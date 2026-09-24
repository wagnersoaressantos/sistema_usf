from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Prefetch

from django.utils import timezone
from datetime import date, timedelta

# Importando a segurança e modelos base do Core
from core.decorators import admin_required
from core.models import MicroArea, Paciente, PacienteCondicao
from territorializacao.services import preencher_automatico_ssa2

# Importando as nossas próprias Tabelas
from .models import FamiliaScore, FichaSSA2, Logradouro, SentinelaRisco, FamiliaSentinela, MembroSentinela, VinculoLogradouro

# ==============================================================================
# TERRITORIALIZAÇÃO E FAMÍLIAS (SCORE DE RISCO)
# ==============================================================================

@login_required
def familias_score(request):
    usf = request.user.perfil.usf_ativa_padrao
    
    if request.method == 'POST' and request.POST.get('acao') == 'recalcular':
        familias = FamiliaScore.objects.filter(usf=usf)
        for f in familias:
            f.salvar_com_score()
        messages.success(request, "Todos os scores foram recalculados com sucesso!")
        return redirect('territorializacao:familias_score')

    q = request.GET.get('q', '')
    classificacao_filtro = request.GET.get('classificacao', '')
    microarea_filtro = request.GET.get('microarea', '') 

    familias = FamiliaScore.objects.filter(usf=usf).order_by('-score_total')
    
    if q:
        familias = familias.filter(nome_responsavel__icontains=q)
    if classificacao_filtro:
        familias = familias.filter(classificacao=classificacao_filtro)
    
    if microarea_filtro:
        cpfs_da_micro = Paciente.objects.filter(micro_area_id=microarea_filtro, usf=usf).values_list('cpf_responsavel', flat=True)
        familias = familias.filter(cpf_responsavel__in=cpfs_da_micro)

    totais = FamiliaScore.objects.filter(usf=usf).values('classificacao').annotate(total=Count('id'))
    dict_totais = {item['classificacao']: item['total'] for item in totais}

    microareas = MicroArea.objects.filter(usf=usf, ativo=True).order_by('codigo')

    context = {
        'familias': familias,
        'totais': dict_totais,
        'q': q,
        'classificacao_filtro': classificacao_filtro,
        'microarea_filtro': microarea_filtro,
        'microareas': microareas,
        'classificacoes': FamiliaScore.CLASSIFICACOES,
        'usf': usf
    }
    # Atualizado para ler da nova pasta
    return render(request, 'territorializacao/familias_score.html', context)

@login_required
def familia_detalhe(request, cpf_responsavel):
    usf = request.user.perfil.usf_ativa_padrao
    familia = get_object_or_404(FamiliaScore, cpf_responsavel=cpf_responsavel, usf=usf)
    
    if request.method == 'POST':
        if request.POST.get('acao') == 'recalcular':
            familia.salvar_com_score()
            messages.success(request, "Score da família sincronizado com as idades e doenças mais recentes!")
            return redirect('territorializacao:familia_detalhe', cpf_responsavel=cpf_responsavel)

        comodos_str = request.POST.get('numero_comodos')
        familia.numero_comodos = int(comodos_str) if comodos_str and comodos_str.isdigit() else None
        familia.save()
        
        FamiliaSentinela.objects.filter(familia=familia).delete()
        MembroSentinela.objects.filter(familia=familia).delete()

        for key, value in request.POST.items():
            if key.startswith('dom_'):
                s_id = key.split('_')[1]
                FamiliaSentinela.objects.create(familia=familia, sentinela_id=s_id, registrado_por=request.user)
            elif key.startswith('ind_'):
                parts = key.split('_')
                p_id = parts[1]
                s_id = parts[2]
                MembroSentinela.objects.create(familia=familia, paciente_id=p_id, sentinela_id=s_id, registrado_por=request.user)
        
        familia.salvar_com_score()
        messages.success(request, f"Avaliação da família de {familia.nome_responsavel} atualizada!")
        return redirect('territorializacao:familia_detalhe', cpf_responsavel=cpf_responsavel)

    sentinelas_dom = SentinelaRisco.objects.filter(tipo='domicilio', ativo=True)
    sentinelas_ind = SentinelaRisco.objects.filter(tipo='individual', ativo=True)
    sentinelas_auto = SentinelaRisco.objects.filter(tipo__in=['idade', 'condicao'], ativo=True)
    
    dom_marcadas = FamiliaSentinela.objects.filter(familia=familia).values_list('sentinela_id', flat=True)
    
    membros = Paciente.objects.filter(cpf_responsavel=cpf_responsavel, usf=usf, ativo=True, obito=False)
    for m in membros:
        m.marcadas_ids = MembroSentinela.objects.filter(familia=familia, paciente=m).values_list('sentinela_id', flat=True)

    context = {
        'familia': familia,
        'sentinelas_dom': sentinelas_dom,
        'sentinelas_ind': sentinelas_ind,
        'sentinelas_auto': sentinelas_auto,
        'dom_marcadas': list(dom_marcadas),
        'membros': membros,
    }
    # Atualizado para ler da nova pasta
    return render(request, 'territorializacao/familia_detalhe.html', context)

@login_required
@admin_required
def territorio_lista(request):
    usf = request.user.perfil.usf_ativa_padrao
    q = request.GET.get('q', '')
    ordenar = request.GET.get('ordenar', 'rua')
    
    context = {'q': q, 'ordenar': ordenar, 'usf': usf}
    
    if ordenar == 'microarea':
        vinculos_query = VinculoLogradouro.objects.select_related('logradouro').order_by('logradouro__logradouro')
        if q:
            vinculos_query = vinculos_query.filter(logradouro__logradouro__icontains=q)
            
        microareas = MicroArea.objects.filter(usf=usf, ativo=True).prefetch_related(
            Prefetch('logradouros_vinculados', queryset=vinculos_query, to_attr='vinculos_filtrados')
        ).order_by('codigo')
        
        context['microareas_agrupadas'] = [ma for ma in microareas if ma.vinculos_filtrados]
        
        ruas_descobertas = Logradouro.objects.filter(usf=usf, vinculos__isnull=True)
        if q: ruas_descobertas = ruas_descobertas.filter(logradouro__icontains=q)
        context['ruas_descobertas'] = ruas_descobertas
        
    else:
        logradouros = Logradouro.objects.filter(usf=usf).prefetch_related('vinculos__micro_area')
        if q: logradouros = logradouros.filter(logradouro__icontains=q)
        context['logradouros'] = logradouros.order_by('logradouro')
        
    # Atualizado para ler da nova pasta
    return render(request, 'territorializacao/territorio_lista.html', context)

@login_required
@admin_required
def admin_rua_salvar(request, pk=None):
    usf = request.user.perfil.usf_ativa_padrao
    rua = get_object_or_404(Logradouro, pk=pk, usf=usf) if pk else None
    
    if request.method == 'POST':
        logradouro_nome = request.POST.get('logradouro')
        bairro = request.POST.get('bairro')
        cep = request.POST.get('cep', '')
        microarea_id = request.POST.get('microarea')
        ativo = request.POST.get('ativo') == 'on'
        
        num_inicial = request.POST.get('numero_inicial')
        num_final = request.POST.get('numero_final')
        
        if not rua:
            rua = Logradouro.objects.create(usf=usf, logradouro=logradouro_nome, bairro=bairro, cep=cep, ativo=ativo)
        else:
            rua.logradouro = logradouro_nome
            rua.bairro = bairro
            rua.cep = cep
            rua.ativo = ativo
            rua.save()
            
        if microarea_id:
            microarea = get_object_or_404(MicroArea, pk=microarea_id, usf=usf)
            vinculo = rua.vinculos.first()
            ignorar_anomalia = request.POST.get('ignorar_anomalia') == 'on'
            
            if vinculo:
                vinculo.micro_area = microarea
                vinculo.numero_inicial = int(num_inicial) if num_inicial and num_inicial.isdigit() else None
                vinculo.numero_final = int(num_final) if num_final and num_final.isdigit() else None
                if ignorar_anomalia:
                    vinculo.motivo = "✔️ Validado (Numeração Correta)"
                elif vinculo.motivo == "✔️ Validado (Numeração Correta)":
                    vinculo.motivo = ""
                vinculo.save()
            else:
                motivo = "✔️ Validado (Numeração Correta)" if ignorar_anomalia else ""
                VinculoLogradouro.objects.create(
                    logradouro=rua, micro_area=microarea, 
                    numero_inicial=int(num_inicial) if num_inicial and num_inicial.isdigit() else None,
                    numero_final=int(num_final) if num_final and num_final.isdigit() else None,
                    motivo=motivo
                )
        else:
            rua.vinculos.all().delete() 
        
        messages.success(request, 'Rua e vínculos atualizados com sucesso!')
        return redirect('territorializacao:territorio_lista')
        
    microareas = MicroArea.objects.filter(usf=usf, ativo=True)
    vinculo_atual = rua.vinculos.first() if rua else None
    
    # Atualizado para ler da nova pasta
    return render(request, 'territorializacao/territorio_rua_form.html', {
        'rua': rua,
        'microareas': microareas,
        'vinculo_atual': vinculo_atual
    })

# ==============================================================================
# MOTOR DO SSA2 (SITUAÇÃO DE SAÚDE)
# ==============================================================================

MESES_OPCOES = [
    (1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'), (4, 'Abril'),
    (5, 'Maio'), (6, 'Junho'), (7, 'Julho'), (8, 'Agosto'),
    (9, 'Setembro'), (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro')
]

@login_required
def painel_ssa2(request):
    usf = request.user.perfil.usf_ativa_padrao
    hoje = date.today()
    
    mes_filtro = int(request.GET.get('mes', hoje.month))
    ano_filtro = int(request.GET.get('ano', hoje.year))
    
    microareas = MicroArea.objects.filter(usf=usf, ativo=True).order_by('codigo')
    
    lista_painel = []
    for ma in microareas:
        ficha = FichaSSA2.objects.filter(microarea=ma, mes=mes_filtro, ano=ano_filtro).first()
        lista_painel.append({
            'microarea': ma,
            'status': 'preenchido' if ficha else 'pendente'
        })
        
    anos_opcoes = [hoje.year, hoje.year - 1, hoje.year - 2]
    
    return render(request, 'territorializacao/painel_ssa2.html', {
        'lista_painel': lista_painel,
        'mes_filtro': mes_filtro,
        'ano_filtro': ano_filtro,
        'meses_opcoes': MESES_OPCOES,
        'anos_opcoes': anos_opcoes
    })

@login_required
def ficha_ssa2_preencher(request, microarea_id):
    usf = request.user.perfil.usf_ativa_padrao
    microarea = get_object_or_404(MicroArea, pk=microarea_id, usf=usf)
    
    hoje = date.today()
    mes_filtro = int(request.GET.get('mes', hoje.month))
    ano_filtro = int(request.GET.get('ano', hoje.year))
    
    ficha_salva = FichaSSA2.objects.filter(microarea=microarea, mes=mes_filtro, ano=ano_filtro).first()
    
    # 🚀 MÁGICA: O MOTOR EXTERNO LÊ OS PACIENTES PARA PREENCHER OS CAMPOS VERDES
    dados_automaticos = preencher_automatico_ssa2(microarea.id, mes_filtro, ano_filtro) or {}

    if request.method == 'POST':
        if not ficha_salva:
            ficha_salva = FichaSSA2(microarea=microarea, mes=mes_filtro, ano=ano_filtro)
            
        # Puxar todos os campos do formulário e salvar
        for campo in request.POST:
            if hasattr(ficha_salva, campo) and request.POST.get(campo):
                setattr(ficha_salva, campo, int(request.POST.get(campo)))
                
        # Garante que os automáticos são salvos se o ACS não os digitou
        for campo_auto, valor_auto in dados_automaticos.items():
            if not getattr(ficha_salva, campo_auto):
                setattr(ficha_salva, campo_auto, valor_auto)
                
        ficha_salva.save()
        messages.success(request, f'Ficha SSA2 da MA {microarea.codigo} salva com sucesso!')
        
        # 🚀 CORREÇÃO AQUI: Usar reverse para achar a URL dinâmica
        from django.urls import reverse
        url_painel = reverse('territorializacao:painel_ssa2')
        return redirect(f"{url_painel}?mes={mes_filtro}&ano={ano_filtro}")

    nome_mes = dict(MESES_OPCOES).get(mes_filtro, '')

    return render(request, 'territorializacao/ficha_ssa2.html', {
        'microarea': microarea,
        'ficha_salva': ficha_salva,
        'dados_automaticos': dados_automaticos,
        'mes_filtro': mes_filtro,
        'ano_filtro': ano_filtro,
        'nome_mes': nome_mes,
        'ano': ano_filtro,
    })

@login_required
def carga_geral_ssa2(request):
    """Salva automaticamente todas as fichas pendentes do mês usando os dados do e-SUS."""
    mes = int(request.GET.get('mes'))
    ano = int(request.GET.get('ano'))
    usf = request.user.perfil.usf_ativa_padrao
    
    microareas = MicroArea.objects.filter(usf=usf, ativo=True)
    count = 0
    for ma in microareas:
        ficha, created = FichaSSA2.objects.get_or_create(microarea=ma, mes=mes, ano=ano)
        
        # 🚀 AGORA A CARGA GERAL VERDADEIRAMENTE PREENCHE OS DADOS SOZINHA!
        dados_auto = preencher_automatico_ssa2(ma.id, mes, ano)
        if dados_auto:
            for campo, valor in dados_auto.items():
                if not getattr(ficha, campo): # Só escreve se o ACS não tiver preenchido ainda
                    setattr(ficha, campo, valor)
            ficha.save()
            if created:
                count += 1
            
    messages.success(request, f'{count} fichas criadas e pré-preenchidas com sucesso para o mês {mes}/{ano}. As outras já estavam prontas.')
    
    from django.urls import reverse
    url_painel = reverse('territorializacao:painel_ssa2')
    return redirect(f"{url_painel}?mes={mes}&ano={ano}")

@login_required
def consolidado_geral_ssa2(request):
    """
    Consolidado Geral da USF (Formato Oficial SIAB/SSA2).
    Soma automaticamente os dados de todas as micro-áreas.
    """
    usf = request.user.perfil.usf_ativa_padrao
    ano_atual = date.today().year
    ano_filtro = int(request.GET.get('ano', ano_atual))

    # 🚀 ORDEM EXATA E OFICIAL DO PAPEL (Importado do Beta)
    estrutura = [
        ('CRIANÇAS', 'Nascidos vivos no mês', 'nascidos_vivos_mes'),
        ('CRIANÇAS', 'RN pesados ao nascer', 'rn_pesados_ao_nascer'),
        ('CRIANÇAS', 'RN pesados com peso < 2.500g', 'rn_baixo_peso'),
        ('CRIANÇAS', 'De 0 a 3 meses e 29 dias (Auto)', 'cria_0_3m_total'),
        ('CRIANÇAS', '↳ 0 a 3 meses: Aleitamento exclusivo', 'cria_0_3m_aleitamento_exclusivo'),
        ('CRIANÇAS', '↳ 0 a 3 meses: Aleitamento misto/outro', 'cria_0_3m_aleitamento_misto'),
        ('CRIANÇAS', 'De 0 a 11 meses e 29 dias (Auto)', 'cria_0_11m_total'),
        ('CRIANÇAS', '↳ Com vacinas em dia', 'cria_0_11m_vacina_em_dia'),
        ('CRIANÇAS', '↳ Pesadas', 'cria_0_11m_pesadas'),
        ('CRIANÇAS', '↳ Desnutridas', 'cria_0_11m_desnutridas'),
        ('CRIANÇAS', 'De 12 a 23 meses e 29 dias (Auto)', 'cria_12_23m_total'),
        ('CRIANÇAS', '↳ Com vacinas em dia', 'cria_12_23m_vacina_em_dia'),
        ('CRIANÇAS', '↳ Pesadas', 'cria_12_23m_pesadas'),
        ('CRIANÇAS', '↳ Desnutridas', 'cria_12_23m_desnutridas'),
        ('CRIANÇAS', 'Menores de 2 anos (Auto)', 'cria_menor_2a_total'),
        ('CRIANÇAS', '↳ Que tiveram diarreia', 'cria_menor_2a_diarreia'),
        ('CRIANÇAS', '↳ Diarreia e usaram TRO', 'cria_menor_2a_diarreia_tro'),
        ('CRIANÇAS', '↳ Infecção Respiratória Aguda (IRA)', 'cria_menor_2a_ira'),
        
        ('GESTANTES', 'Cadastradas (Auto)', 'gest_cadastradas'),
        ('GESTANTES', 'Acompanhadas', 'gest_acompanhadas'),
        ('GESTANTES', 'Com vacina em dia', 'gest_vacina_em_dia'),
        ('GESTANTES', 'Fez consulta de pré-natal no mês', 'gest_consulta_mes'),
        ('GESTANTES', 'Com pré-natal iniciado no 1º TRI', 'gest_inicio_1_trimestre'),
        ('GESTANTES', '< 20 anos cadastradas (Auto)', 'gest_menor_20_anos'),
        
        ('DOENÇAS', 'Diabéticos: Cadastrados (Auto)', 'diab_cadastrados'),
        ('DOENÇAS', 'Diabéticos: Acompanhados', 'diab_acompanhados'),
        ('DOENÇAS', 'Hipertensos: Cadastrados (Auto)', 'hiper_cadastrados'),
        ('DOENÇAS', 'Hipertensos: Acompanhados', 'hiper_acompanhados'),
        ('DOENÇAS', 'Tuberculose: Cadastrados (Auto)', 'tb_cadastrados'),
        ('DOENÇAS', 'Tuberculose: Acompanhados', 'tb_acompanhados'),
        ('DOENÇAS', 'Hanseníase: Cadastrados (Auto)', 'han_cadastrados'),
        ('DOENÇAS', 'Hanseníase: Acompanhados', 'han_acompanhados'),
        
        ('HOSPITALIZADOS', '< 5 anos por pneumonia', 'hosp_menor_5a_pneumonia'),
        ('HOSPITALIZADOS', '< 5 anos por desidratação', 'hosp_menor_5a_desidratacao'),
        ('HOSPITALIZADOS', 'Por abuso de álcool', 'hosp_abuso_alcool'),
        ('HOSPITALIZADOS', 'Por complicação da Diabetes', 'hosp_complicacao_diabetes'),
        ('HOSPITALIZADOS', 'Por outras causas', 'hosp_outras_causas'),
        ('HOSPITALIZADOS', 'Total de Internações', 'hosp_total'),
        ('HOSPITALIZADOS', 'Internações em hospital psiquiátrico', 'hosp_psiquiatrico'),
        
        ('ÓBITOS', 'De menores de 28 dias: Por diarreia', 'obito_menor_28d_diarreia'),
        ('ÓBITOS', 'De menores de 28 dias: Por IRA', 'obito_menor_28d_ira'),
        ('ÓBITOS', 'De menores de 28 dias: Por outras causas', 'obito_menor_28d_outras'),
        ('ÓBITOS', 'De 28 dias a 11 meses: Por diarreia', 'obito_28d_11m_diarreia'),
        ('ÓBITOS', 'De 28 dias a 11 meses: Por IRA', 'obito_28d_11m_ira'),
        ('ÓBITOS', 'De 28 dias a 11 meses: Por outras', 'obito_28d_11m_outras'),
        ('ÓBITOS', 'De menores de 1 ano: Por diarreia', 'obito_menor_1a_diarreia'),
        ('ÓBITOS', 'De menores de 1 ano: Por IRA', 'obito_menor_1a_ira'),
        ('ÓBITOS', 'De menores de 1 ano: Por outras', 'obito_menor_1a_outras'),
        ('ÓBITOS', 'Mulheres de 10 a 14 anos (Auto)', 'obito_mulher_10_14a'),
        ('ÓBITOS', 'Mulheres de 15 a 49 anos (Auto)', 'obito_mulher_15_49a'),
        ('ÓBITOS', 'Outros óbitos', 'obito_outras_causas'),
        ('ÓBITOS', 'Total de óbitos (Auto)', 'obito_total'),
        ('ÓBITOS', 'Adolescentes (10-19 anos) por violência', 'obito_adolescente_violencia'),
        
        ('GERAIS', 'Total de famílias cadastradas (Auto)', 'total_familias_cadastradas'),
        ('GERAIS', 'Visita domiciliar - ACS', 'visita_domiciliar_acs'),
    ]

    matriz = []
    categoria_atual = None
    
    for cat, rotulo, campo in estrutura:
        linha = {
            'categoria': cat,
            'nova_categoria': (cat != categoria_atual),
            'rotulo': rotulo,
            'meses': [],
            'total_anual': 0
        }
        categoria_atual = cat
        
        for mes in range(1, 13):
            # Soma todas as fichas de todas as micro-áreas para formar a linha
            fichas = FichaSSA2.objects.filter(microarea__usf=usf, mes=mes, ano=ano_filtro)
            soma_mes = sum(getattr(f, campo) or 0 for f in fichas)
            linha['meses'].append(soma_mes if soma_mes > 0 else '-')
            linha['total_anual'] += soma_mes
            
        matriz.append(linha)
        
    return render(request, 'territorializacao/consolidado_geral_ssa2.html', {
        'usf': usf,
        'ano_filtro': ano_filtro,
        'anos': [ano_atual, ano_atual - 1],
        'meses_labels': ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'],
        'matriz': matriz
    })