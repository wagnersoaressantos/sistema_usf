import csv
import re
from datetime import datetime
from django.utils import timezone
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q

from core.decorators import admin_required
from core.models import CondicaoSaude, EquipeUSF, Paciente, MicroArea, PacienteCondicao
from territorializacao.models import FamiliaScore, Logradouro, VinculoLogradouro
from farmacia.models import Medicamento

@login_required
@admin_required
def hub_importacoes(request):
    """Painel central onde o gestor escolhe o que quer importar."""
    condicoes = CondicaoSaude.objects.filter(ativo=True).order_by('nome')
    return render(request, 'importacoes/hub.html', {'condicoes': condicoes})

@login_required
@admin_required
def importar_pacientes_csv(request):
    """Lê o ficheiro CSV do e-SUS e prepara para salvar os pacientes (Vinculados)."""
    
    vinculo = EquipeUSF.objects.filter(user=request.user, ativo=True).select_related('usf').first()
    usf = vinculo.usf if vinculo else None

    if request.method == 'POST':
        ficheiro = request.FILES.get('arquivo_csv')
        
        if not ficheiro:
            messages.error(request, 'Por favor, selecione um ficheiro CSV.')
            return redirect('importacoes:hub')
            
        if not ficheiro.name.endswith('.csv'):
            messages.error(request, 'Formato inválido. O ficheiro tem de ser um .csv!')
            return redirect('importacoes:hub')

        try:
            conteudo = ficheiro.read()
            
            # TENTATIVA BLINDADA DE DESCODIFICAÇÃO
            try:
                dados_texto = conteudo.decode('utf-8-sig') 
            except UnicodeDecodeError:
                try:
                    dados_texto = conteudo.decode('latin-1') 
                except UnicodeDecodeError:
                    dados_texto = conteudo.decode('utf-16', errors='replace') 
                    
            linhas_todas = dados_texto.splitlines()
            
            linhas_validas = []
            achou_tabela = False
            
            for linha in linhas_todas:
                if 'Nome equipe' in linha and 'Microárea' in linha:
                    achou_tabela = True
                if achou_tabela:
                    linhas_validas.append(linha)
                    
            if not linhas_validas:
                messages.error(request, 'Não foi possível encontrar as colunas no ficheiro. Verifique se é o relatório de "Cidadãos Vinculados".')
                return redirect('importacoes:hub')

            leitor_csv = csv.DictReader(linhas_validas, delimiter=';')
            
            # Sincronização de Estado (State Syncing)
            Paciente.objects.filter(usf=usf, ativo=True).update(atualizado=False)
            
            total_criados = 0
            total_atualizados = 0
            
            with transaction.atomic():
                
                for row in leitor_csv:
                    documento_bruto = row.get('CPF/CNS', '')
                    apenas_numeros = re.sub(r'\D', '', documento_bruto) 
                    
                    if not apenas_numeros:
                        continue 
                        
                    cpf = apenas_numeros if len(apenas_numeros) == 11 else None
                    cartao_sus = apenas_numeros if len(apenas_numeros) == 15 else None
                    
                    ma_codigo = str(row.get('Microárea', '')).strip()
                    microarea_obj = None
                    if ma_codigo and ma_codigo.isdigit():
                        microarea_obj, _ = MicroArea.objects.get_or_create(usf=usf, codigo=ma_codigo.zfill(2))

                    nome = str(row.get('Nome', '')).strip()
                    sexo_csv = str(row.get('Sexo', '')).strip().lower()
                    sexo = 'F' if 'feminino' in sexo_csv else 'M' if 'masculino' in sexo_csv else 'I'
                    
                    data_nascimento = None
                    data_str = str(row.get('Data de nascimento', '')).strip()
                    if data_str:
                        try:
                            data_nascimento = datetime.strptime(data_str, '%d/%m/%Y').date()
                        except ValueError:
                            pass
                            
                    endereco_completo = str(row.get('Endereço', '')).strip()
                    telefone = re.sub(r'\D', '', str(row.get('Telefone celular', '')))[:11]
                    
                    paciente = None
                    if cpf:
                        paciente = Paciente.objects.filter(cpf=cpf, usf=usf).first()
                    if not paciente and cartao_sus:
                        paciente = Paciente.objects.filter(cartao_sus=cartao_sus, usf=usf).first()
                        
                    if paciente:
                        # 🚀 CORREÇÃO: Achamos o paciente no CSV! Atualizamos os dados básicos dele.
                        paciente.nome = nome
                        paciente.sexo = sexo
                        if data_nascimento:
                            paciente.data_nascimento = data_nascimento
                        if endereco_completo:
                            paciente.endereco = endereco_completo
                        if telefone:
                            paciente.telefone = telefone
                        if microarea_obj:
                            paciente.micro_area = microarea_obj
                        
                        # Avisamos o sistema que este paciente continua vivo e frequenta a USF
                        paciente.atualizado = True
                        paciente.ultima_atualizacao = timezone.now()
                        paciente.save()
                        
                        total_atualizados += 1
                        
                    else:
                        Paciente.objects.create(
                            usf=usf, micro_area=microarea_obj, nome=nome, cpf=cpf,
                            cartao_sus=cartao_sus, data_nascimento=data_nascimento, sexo=sexo,
                            endereco=endereco_completo, telefone=telefone, cadastrado_por=request.user,
                            atualizado=True, ultima_atualizacao=timezone.now()
                        )
                        total_criados += 1
                
            messages.success(request, f'Ficheiro processado! {total_criados} novos pacientes criados e {total_atualizados} cadastros atualizados.')
            return redirect('importacoes:hub')
            
        except Exception as e:
            messages.error(request, f'Erro ao processar ficheiro: {str(e)}')
            return redirect('importacoes:hub')

    return redirect('importacoes:hub')

@login_required
@admin_required
def importar_condicoes_csv(request):
    """Lê o relatório temático do e-SUS e vincula a Doença/Condição escolhida aos pacientes."""
    usf = EquipeUSF.objects.filter(user=request.user, ativo=True).first().usf

    if request.method == 'POST':
        ficheiro = request.FILES.get('arquivo_csv')
        # CORREÇÃO 1: O HTML manda "condicao_saude" e não "condicao_id"
        condicao_id = request.POST.get('condicao_saude')
        
        if not ficheiro or not condicao_id:
            # CORREÇÃO 2: Mensagem mais profissional
            messages.error(request, 'Faltou selecionar o ficheiro CSV ou a Lista Temática.')
            return redirect('importacoes:hub')
            
        condicao_escolhida = get_object_or_404(CondicaoSaude, pk=condicao_id)

        try:
            conteudo = ficheiro.read()
            try:
                dados_texto = conteudo.decode('utf-8-sig') 
            except UnicodeDecodeError:
                try:
                    dados_texto = conteudo.decode('latin-1') 
                except UnicodeDecodeError:
                    dados_texto = conteudo.decode('utf-16', errors='replace') 
                    
            linhas_todas = dados_texto.splitlines()
            linhas_validas = []
            achou_tabela = False
            for linha in linhas_todas:
                if 'Nome;' in linha and ('CPF;' in linha or 'CNS;' in linha):
                    achou_tabela = True
                if achou_tabela:
                    linhas_validas.append(linha)
                    
            if not linhas_validas:
                messages.error(request, 'Não foi possível ler as colunas. Verifique o CSV.')
                return redirect('importacoes:hub')

            leitor_csv = csv.DictReader(linhas_validas, delimiter=';')
            
            doentes_atuais_ids = set(PacienteCondicao.objects.filter(
                paciente__usf=usf, condicao=condicao_escolhida, data_fim__isnull=True
            ).values_list('paciente_id', flat=True))
            
            pacientes_encontrados_no_csv = set()
            total_novos_diagnosticos = 0
            
            with transaction.atomic():
                for row in leitor_csv:
                    cpf_bruto = re.sub(r'\D', '', str(row.get('CPF', '')))
                    cns_bruto = re.sub(r'\D', '', str(row.get('CNS', '')))
                    
                    cpf = cpf_bruto if len(cpf_bruto) == 11 else None
                    cns = cns_bruto if len(cns_bruto) == 15 else None
                    
                    paciente = None
                    if cpf:
                        paciente = Paciente.objects.filter(cpf=cpf, usf=usf).first()
                    if not paciente and cns:
                        paciente = Paciente.objects.filter(cartao_sus=cns, usf=usf).first()
                        
                    if paciente:
                        pacientes_encontrados_no_csv.add(paciente.id)
                        if paciente.id not in doentes_atuais_ids:
                            PacienteCondicao.objects.create(
                                paciente=paciente, condicao=condicao_escolhida,
                                data_inicio=timezone.now().date(), observacao='Importação do e-SUS PEC'
                            )
                            total_novos_diagnosticos += 1
                            
                pacientes_curados_ids = doentes_atuais_ids - pacientes_encontrados_no_csv
                if pacientes_curados_ids:
                    PacienteCondicao.objects.filter(
                        paciente_id__in=pacientes_curados_ids, condicao=condicao_escolhida, data_fim__isnull=True
                    ).update(
                        data_fim=timezone.now().date(), observacao='Encerrada via sincronização'
                    )
                    
            messages.success(request, f'Condição "{condicao_escolhida.nome}" sincronizada! {total_novos_diagnosticos} novos, {len(pacientes_curados_ids)} altas.')
            return redirect('importacoes:hub')
            
        except Exception as e:
            messages.error(request, f'Erro grave ao processar ficheiro: {str(e)}')
            return redirect('importacoes:hub')

    return redirect('importacoes:hub')

@login_required
@admin_required
def importar_territorio_csv(request):
    """
    Usa o relatório 'Acompanhamento do Território' para mapear Ruas,
    criar Famílias, vincular Pacientes e MAPEAR A NUMERAÇÃO das casas!
    """
    usf = EquipeUSF.objects.filter(user=request.user, ativo=True).first().usf

    if request.method == 'POST':
        ficheiro = request.FILES.get('arquivo_csv')
        
        if not ficheiro or not ficheiro.name.endswith('.csv'):
            messages.error(request, 'Envie um ficheiro .csv válido gerado pelo e-SUS!')
            return redirect('importacoes:hub')

        try:
            conteudo = ficheiro.read()
            try:
                dados_texto = conteudo.decode('utf-8-sig') 
            except UnicodeDecodeError:
                try:
                    dados_texto = conteudo.decode('latin-1') 
                except UnicodeDecodeError:
                    dados_texto = conteudo.decode('utf-16', errors='replace') 
                    
            linhas_todas = dados_texto.splitlines()
            linhas_validas = []
            achou_tabela = False
            micro_str = None
            
            for linha in linhas_todas:
                if linha.startswith('Microárea;'):
                    match = re.search(r'\d+', linha.split(';')[1])
                    if match: micro_str = match.group()
                        
                if 'TIPO DE LOGRADOURO;' in linha and 'LOGRADOURO;' in linha:
                    achou_tabela = True
                if achou_tabela:
                    linhas_validas.append(linha)
                    
            if not linhas_validas:
                messages.error(request, 'Não foi possível ler as colunas. Use o relatório "Acompanhamento do Território".')
                return redirect('importacoes:hub')

            leitor_csv = csv.DictReader(linhas_validas, delimiter=';')
            
            ruas_criadas, familias_criadas, pacientes_atualizados = 0, 0, 0
            
            # 🚀 NOVO: Dicionário para guardar os números encontrados em cada rua
            # Ex: { id_do_vinculo: set(10, 14, 18, 935) }
            numeros_por_vinculo = {}
            
            with transaction.atomic():
                micro_area = None
                if micro_str:
                    micro_area, _ = MicroArea.objects.get_or_create(usf=usf, codigo=micro_str.zfill(2))

                for row in leitor_csv:
                    nome_cidadao = row.get('NOME CIDADÃO', '').strip()
                    if not nome_cidadao or nome_cidadao == '-': continue 
                        
                    tipo_log = row.get('TIPO DE LOGRADOURO', '').strip()
                    nome_log = row.get('LOGRADOURO', '').strip()
                    rua_nome = f"{tipo_log} {nome_log}".strip() if tipo_log else nome_log
                    
                    bairro = row.get('BAIRRO', '').strip()
                    numero = row.get('NÚMERO', '').strip()
                    cep = re.sub(r'\D', '', row.get('CEP', ''))

                    # 1. GEOGRAFIA BÁSICA
                    logradouro, created = Logradouro.objects.get_or_create(
                        usf=usf, logradouro=rua_nome, bairro=bairro, defaults={'cep': cep, 'ativo': True}
                    )
                    if created: ruas_criadas += 1

                    if micro_area:
                        vinculo, _ = VinculoLogradouro.objects.get_or_create(logradouro=logradouro, micro_area=micro_area)
                        
                        # 🚀 EXTRAI O NÚMERO DA CASA E GUARDA NO "BALDE" DESTA RUA
                        num_limpo = re.sub(r'\D', '', numero) # Ex: 1050A -> 1050
                        if num_limpo:
                            if vinculo.id not in numeros_por_vinculo:
                                numeros_por_vinculo[vinculo.id] = set()
                            numeros_por_vinculo[vinculo.id].add(int(num_limpo))

                    # 2. FAMÍLIAS
                    eh_responsavel = row.get('É O RESPONSÁVEL FAMILIAR?', '').strip().upper() == 'SIM'
                    cpf_resp_bruto = row.get('CPF/CNS RESPONSÁVEL FAMILIAR', '')
                    cpf_resp_limpo = re.sub(r'\D', '', cpf_resp_bruto)[:11] 
                    nome_resp = row.get('NOME DO RESPONSÁVEL FAMILIAR', '').strip()
                    
                    if eh_responsavel and cpf_resp_limpo:
                        _, fam_created = FamiliaScore.objects.get_or_create(
                            usf=usf, cpf_responsavel=cpf_resp_limpo,
                            defaults={'nome_responsavel': nome_cidadao, 'logradouro': rua_nome, 'numero': numero, 'bairro': bairro, 'cep': cep}
                        )
                        if fam_created: familias_criadas += 1

                    # 3. PACIENTES
                    cpf_bruto = re.sub(r'\D', '', str(row.get('CPF', '')))
                    cns_bruto = re.sub(r'\D', '', str(row.get('CNS', '')))
                    cpf = cpf_bruto if len(cpf_bruto) == 11 else None
                    cns = cns_bruto if len(cns_bruto) == 15 else None
                    
                    paciente = None
                    if cpf: paciente = Paciente.objects.filter(cpf=cpf, usf=usf).first()
                    if not paciente and cns: paciente = Paciente.objects.filter(cartao_sus=cns, usf=usf).first()
                        
                    if paciente:
                        paciente.endereco = rua_nome
                        paciente.numero = numero
                        paciente.micro_area = micro_area
                        paciente.responsavel_familiar = eh_responsavel
                        if cpf_resp_limpo: paciente.cpf_responsavel = cpf_resp_limpo
                            
                        paciente.save(update_fields=['endereco', 'numero', 'micro_area', 'responsavel_familiar', 'cpf_responsavel'])
                        pacientes_atualizados += 1
                        
                # 🚀 PÓS-PROCESSAMENTO MÁGICO: AVALIAR TODOS OS NÚMEROS DAS RUAS
                for vinculo_id, numeros_set in numeros_por_vinculo.items():
                    if not numeros_set: continue
                        
                    numeros_ordenados = sorted(list(numeros_set))
                    min_num = numeros_ordenados[0]
                    max_num = numeros_ordenados[-1]
                    
                    vinculo_obj = VinculoLogradouro.objects.get(id=vinculo_id)
                    
                    # 🚀 NOVO: Se o Gestor já validou que esta rua é maluca, o robô respeita!
                    if vinculo_obj.motivo == "✔️ Validado (Numeração Correta)":
                        vinculo_obj.numero_inicial = min_num
                        vinculo_obj.numero_final = max_num
                        vinculo_obj.save(update_fields=['numero_inicial', 'numero_final'])
                        continue # Pula a validação de anomalias
                    
                    alertas_salto = []
                    # Verifica se há "buracos" suspeitos maiores que 300 entre duas casas
                    for i in range(1, len(numeros_ordenados)):
                        salto = numeros_ordenados[i] - numeros_ordenados[i-1]
                        if salto > 300:
                            alertas_salto.append(f"{numeros_ordenados[i-1]}➔{numeros_ordenados[i]}")
                            
                    vinculo_obj = VinculoLogradouro.objects.get(id=vinculo_id)
                    vinculo_obj.numero_inicial = min_num
                    vinculo_obj.numero_final = max_num
                    
                    if alertas_salto:
                        vinculo_obj.motivo = f"⚠️ ERRO NUMERAÇÃO: Salto suspeito de {' | '.join(alertas_salto)}"
                    else:
                        vinculo_obj.motivo = "" # Limpa se o erro foi corrigido
                        
                    vinculo_obj.save(update_fields=['numero_inicial', 'numero_final', 'motivo'])

            messages.success(request, f'Sucesso! {ruas_criadas} ruas mapeadas, {familias_criadas} famílias e {pacientes_atualizados} pacientes vinculados.')
            return redirect('importacoes:hub')
            
        except Exception as e:
            messages.error(request, f'Erro grave ao processar ficheiro de território: {str(e)}')
            return redirect('importacoes:hub')

    return redirect('importacoes:hub')

@login_required
@admin_required
def importar_farmacia_csv(request):
    """
    O Leitor Inteligente do Catálogo (REMUME).
    Lê o Código BR e o Nome. Descobre sozinho se é Insumo ou Remédio.
    """
    if request.method == 'POST':
        ficheiro = request.FILES.get('arquivo_csv')
        
        if not ficheiro or not ficheiro.name.endswith('.csv'):
            messages.error(request, 'Envie um ficheiro .csv com o catálogo.')
            return redirect('importacoes:hub')

        try:
            conteudo = ficheiro.read()
            try: dados_texto = conteudo.decode('utf-8-sig') 
            except UnicodeDecodeError: dados_texto = conteudo.decode('latin-1') 

            # Palavras-chave para o Robô descobrir se é Material/Insumo
            palavras_insumo = ['SERINGA', 'AGULHA', 'ATADURA', 'LUVA', 'CATETER', 'LANCETA', 'TERMOMETRO', 'ESPARADRAPO', 'COLETOR', 'ALGODÃO', 'ÁLCOOL', 'AVENTAL', 'COMPRESSA', 'FRASCO', 'TIRA REAGENTE', 'GEL']
            
            linhas_todas = dados_texto.splitlines()
            leitor_csv = csv.reader(linhas_todas, delimiter=';')
            
            criados, atualizados = 0, 0
            
            with transaction.atomic():
                for row in leitor_csv:
                    if len(row) < 2: continue # Ignora linhas vazias
                    
                    codigo_br = str(row[0]).strip()
                    nome_completo = str(row[1]).strip().upper()
                    
                    if not codigo_br or codigo_br == 'CÓDIGO' or 'PRODUTO' in nome_completo:
                        continue # Pula o cabeçalho
                        
                    # Inteligência: É Insumo ou Medicamento?
                    tipo_item = None
                    forma_farmaceutica = None
                    
                    for palavra in palavras_insumo:
                        if palavra in nome_completo:
                            tipo_item = 'INS'
                            forma_farmaceutica = 'UNID'
                            break
                    
                    # 🚀 MÁGICA: Se não for insumo, tenta descobrir a forma pela palavra
                    if not tipo_item:
                        if 'XAROPE' in nome_completo:
                            tipo_item = 'MED'
                            forma_farmaceutica = 'XARO'
                        elif 'SOLUÇÃO ORAL' in nome_completo or 'GOTAS' in nome_completo or 'SUSPENSÃO' in nome_completo or 'ELIXIR' in nome_completo:
                            tipo_item = 'MED'
                            forma_farmaceutica = 'GOTA'
                        elif 'INJETÁVEL' in nome_completo or 'INJETAVEL' in nome_completo:
                            tipo_item = 'MED'
                            forma_farmaceutica = 'INJE'
                        elif 'POMADA' in nome_completo or 'CREME' in nome_completo or 'GEL' in nome_completo:
                            tipo_item = 'MED'
                            forma_farmaceutica = 'POMA'
                        elif 'CAPSULA' in nome_completo:
                            tipo_item = 'MED'
                            forma_farmaceutica = 'CAPS'
                        elif 'COMPRIMIDO' in nome_completo or 'DRAGEA' in nome_completo:
                            tipo_item = 'MED'
                            forma_farmaceutica = 'COMP'
                            
                    # 🚀 A MÁGICA DA CURADORIA: Se o robô não tem certeza de tudo, cadastra Inativo!
                    item_ativo = True if tipo_item and forma_farmaceutica else False

                    # Busca ou Cria
                    med, created = Medicamento.objects.get_or_create(
                        codigo_br=codigo_br,
                        defaults={
                            'nome': nome_completo,
                            'tipo': tipo_item,
                            'forma_farmaceutica': forma_farmaceutica,
                            'ativo': item_ativo
                        }
                    )
                    
                    if created:
                        criados += 1
                    else:
                        med.nome = nome_completo # Atualiza o nome caso tenha mudado na planilha
                        # Se já estava cadastrado e o robô achou algo novo, preenche
                        if not med.tipo: med.tipo = tipo_item
                        if not med.forma_farmaceutica: med.forma_farmaceutica = forma_farmaceutica
                        
                        # Atenção: Ele NUNCA desativa um item que o Gestor Humano já ativou!
                        if not med.ativo and item_ativo:
                            med.ativo = True
                            
                        med.save()
                        atualizados += 1

            messages.success(request, f'✅ Catálogo importado! {criados} novos itens cadastrados e {atualizados} atualizados.')
            
        except Exception as e:
            messages.error(request, f'Erro ao ler catálogo: {str(e)}')
            
    return redirect('importacoes:hub')