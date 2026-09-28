from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.contrib import messages
from datetime import date, timedelta
from django.db import transaction
from django.core.exceptions import ValidationError

from core.models import Paciente, EquipeUSF
from .models import LoteEstoque, Dispensacao, ItemDispensacao, Medicamento, DemandaReprimida, MovimentacaoEstoque

# ==============================================================================
# FASE 1: O BALCÃO E O HUB
# ==============================================================================

@login_required
def hub_farmacia(request):
    """O Painel Central da Farmácia."""
    usf = getattr(request.user.perfil, 'usf_ativa_padrao', None)
    
    total_medicamentos = Medicamento.objects.filter(ativo=True).count()
    
    estoque_baixo = 0
    lotes_vencendo = 0
    if usf:
        estoque_baixo = LoteEstoque.objects.filter(usf=usf, quantidade_atual__lt=50, quantidade_atual__gt=0).count()
        limite_validade = date.today() + timedelta(days=90)
        lotes_vencendo = LoteEstoque.objects.filter(usf=usf, quantidade_atual__gt=0, data_validade__lte=limite_validade).count()
        
    return render(request, 'farmacia/hub.html', {
        'usf': usf,
        'total_medicamentos': total_medicamentos,
        'estoque_baixo': estoque_baixo,
        'lotes_vencendo': lotes_vencendo,
    })

@login_required
def balcao_busca(request):
    """O 'Guiché' da Farmácia para procurar pacientes."""
    perfil = getattr(request.user, 'perfil', None)
    usf = perfil.usf_ativa_padrao if perfil else None

    if not usf:
        vinculo = EquipeUSF.objects.filter(user=request.user, ativo=True).first()
        usf = vinculo.usf if vinculo else None

    q = request.GET.get('q', '')
    
    if usf:
        pacientes_query = Paciente.objects.filter(usf=usf, ativo=True, obito=False)
        if q:
            pacientes_query = pacientes_query.filter(
                Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(cartao_sus__icontains=q)
            )
    else:
        pacientes_query = Paciente.objects.none()

    paginator = Paginator(pacientes_query.order_by('nome'), 20)
    page = request.GET.get('page')
    pacientes = paginator.get_page(page)

    return render(request, 'farmacia/balcao.html', {'pacientes': pacientes, 'q': q, 'usf': usf})

@login_required
def atender_receita(request, paciente_id):
    """Entrega o remédio, abate do estoque e aplica a trava antissuperposição."""
    usf = getattr(request.user.perfil, 'usf_ativa_padrao', None)
    paciente = get_object_or_404(Paciente, pk=paciente_id, usf=usf)

    if request.method == 'POST':
        acao = request.POST.get('acao', 'entregar')
        
        # 🚨 SE CLICOU NO BOTÃO VERMELHO DE FALTA:
        if acao == 'falta':
            medicamento_id = request.POST.get('medicamento_falta')
            medicamento_falta = get_object_or_404(Medicamento, pk=medicamento_id)
            
            DemandaReprimida.objects.create(
                usf=usf, paciente=paciente, medicamento=medicamento_falta, profissional=request.user
            )
            messages.warning(request, f'📝 Registrada a falta de {medicamento_falta.nome}. Isto ajudará a cobrar o reabastecimento à Central!')
            return redirect('farmacia:atender_receita', paciente_id=paciente.id)
            
        # ✅ LÓGICA ORIGINAL DE ENTREGA:
        lote_id = request.POST.get('lote')
        quantidade = int(request.POST.get('quantidade', 0))
        posologia = request.POST.get('posologia')
        dias = request.POST.get('dias')
        uso_continuo = request.POST.get('uso_continuo') == 'on'
        justificativa = request.POST.get('justificativa', '').strip()

        lote = get_object_or_404(LoteEstoque, pk=lote_id, usf=usf)

        if quantidade <= 0 or quantidade > lote.quantidade_atual:
            messages.error(request, 'Quantidade inválida ou superior ao estoque disponível!')
            return redirect('farmacia:atender_receita', paciente_id=paciente.id)

        proxima_retirada = None
        if dias and dias.isdigit():
            proxima_retirada = date.today() + timedelta(days=int(dias) - 5)

        ultimo_item = ItemDispensacao.objects.filter(
            dispensacao__paciente=paciente, medicamento=lote.medicamento, data_proxima_retirada__isnull=False
        ).order_by('-data_proxima_retirada').first()

        if ultimo_item and ultimo_item.data_proxima_retirada > date.today():
            if not justificativa:
                messages.warning(request, f'⚠️ BLOQUEIO: O paciente já possui {lote.medicamento.nome}. Próxima retirada autorizada a partir de {ultimo_item.data_proxima_retirada.strftime("%d/%m/%Y")}. Digite uma Justificativa Clínica para forçar a entrega antecipada.')
                return redirect('farmacia:atender_receita', paciente_id=paciente.id)

        dispensacao, _ = Dispensacao.objects.get_or_create(
            paciente=paciente, usf=usf, profissional=request.user, data_dispensacao__date=date.today(),
            defaults={'observacoes': 'Entrega registrada via Balcão.'}
        )

        ItemDispensacao.objects.create(
            dispensacao=dispensacao, medicamento=lote.medicamento, lote_utilizado=lote, quantidade_entregue=quantidade,
            uso_continuo=uso_continuo, posologia_diaria=posologia if posologia else None, dias_tratamento=dias if dias else None,
            data_proxima_retirada=proxima_retirada, justificativa_antecipacao=justificativa
        )

        lote.quantidade_atual -= quantidade
        lote.save()

        messages.success(request, f'✅ {quantidade}x {lote.medicamento.nome} entregue com sucesso!')
        return redirect('farmacia:atender_receita', paciente_id=paciente.id)

    lotes_disponiveis = LoteEstoque.objects.filter(usf=usf, quantidade_atual__gt=0).select_related('medicamento').order_by('medicamento__nome', 'data_validade')
    historico = ItemDispensacao.objects.filter(dispensacao__paciente=paciente).select_related('dispensacao', 'medicamento').order_by('-dispensacao__data_dispensacao')[:30]
    catalogo_geral = Medicamento.objects.filter(ativo=True).order_by('nome')

    return render(request, 'farmacia/atender.html', {
        'paciente': paciente, 'lotes': lotes_disponiveis, 'historico': historico, 'catalogo_geral': catalogo_geral, 'hoje': date.today(),
    })

# ==============================================================================
# FASE 2: GESTÃO DE ESTOQUE E ENTRADAS
# ==============================================================================

@login_required
def estoque_lista(request):
    """Mostra o saldo atual das prateleiras da USF."""
    usf = getattr(request.user.perfil, 'usf_ativa_padrao', None)
    lotes = LoteEstoque.objects.filter(usf=usf, quantidade_atual__gt=0).select_related('medicamento').order_by('medicamento__nome', 'data_validade')
    limite_validade = date.today() + timedelta(days=90)
    
    return render(request, 'farmacia/estoque.html', {'lotes': lotes, 'limite_validade': limite_validade, 'hoje': date.today()})

@login_required
def entrada_lote(request):
    """Registra a chegada de medicamentos da CAF."""
    usf = getattr(request.user.perfil, 'usf_ativa_padrao', None)
    
    if request.method == 'POST':
        medicamento_id = request.POST.get('medicamento')
        numero_lote = request.POST.get('numero_lote', '').strip()
        data_validade = request.POST.get('data_validade')
        quantidade = int(request.POST.get('quantidade', 0))
        justificativa = request.POST.get('justificativa', 'Recebimento de rotina da CAF.')
        
        if quantidade <= 0:
            messages.error(request, 'A quantidade deve ser maior que zero.')
            return redirect('farmacia:entrada_lote')
            
        medicamento = get_object_or_404(Medicamento, pk=medicamento_id, ativo=True)
        
        with transaction.atomic():
            lote, created = LoteEstoque.objects.get_or_create(
                medicamento=medicamento, usf=usf, numero_lote=numero_lote, data_validade=data_validade if data_validade else None,
                defaults={'quantidade_atual': 0}
            )
            
            MovimentacaoEstoque.objects.create(
                lote=lote, tipo_movimento='ENTRADA_CAF', quantidade=quantidade, justificativa=justificativa, registrado_por=request.user
            )
            
        messages.success(request, f'✅ Entrada de {quantidade}x {medicamento.nome} registrada com sucesso!')
        return redirect('farmacia:estoque_lista')
        
    medicamentos = Medicamento.objects.filter(ativo=True).order_by('nome')
    return render(request, 'farmacia/entrada.html', {'medicamentos': medicamentos})

# ==============================================================================
# FASE 3: GESTÃO DO CATÁLOGO (REMUME)
# ==============================================================================

@login_required
def catalogo_lista(request):
    """Tela de gestão para ver e desativar itens."""
    if request.method == 'POST' and request.POST.get('acao') == 'desativar_massa':
        ids_selecionados = request.POST.getlist('itens_selecionados')
        sucessos, erros_estoque = 0, 0
        
        if ids_selecionados:
            for med_id in ids_selecionados:
                try:
                    med = Medicamento.objects.get(pk=med_id)
                    if med.ativo:
                        med.ativo = False
                        med.save()
                        sucessos += 1
                except ValidationError:
                    erros_estoque += 1
                except Medicamento.DoesNotExist:
                    pass
            
            if sucessos > 0: messages.success(request, f'✅ {sucessos} produtos desativados com sucesso.')
            if erros_estoque > 0: messages.warning(request, f'⚠️ {erros_estoque} produtos não puderam ser desativados pois ainda têm saldo!')
        else:
            messages.error(request, 'Selecione pelo menos um item para desativar.')
        return redirect(request.get_full_path())

    q = request.GET.get('q', '')
    tipo_filtro = request.GET.get('tipo', '')
    status_filtro = request.GET.get('status', '')
    
    itens = Medicamento.objects.all()
    if q: itens = itens.filter(Q(nome__icontains=q) | Q(codigo_br__icontains=q))
    if tipo_filtro: itens = itens.filter(tipo=tipo_filtro)
    if status_filtro == 'ativo': itens = itens.filter(ativo=True)
    elif status_filtro == 'inativo': itens = itens.filter(ativo=False)
        
    paginator = Paginator(itens.order_by('nome'), 30)
    page = request.GET.get('page')
    catalogo = paginator.get_page(page)
    
    is_admin = False
    if hasattr(request.user, 'perfil') and request.user.perfil.is_master: is_admin = True
    else:
        usf = getattr(request.user.perfil, 'usf_ativa_padrao', None)
        if usf and EquipeUSF.objects.filter(user=request.user, usf=usf, is_admin_unidade=True, ativo=True).exists(): is_admin = True

    return render(request, 'farmacia/catalogo_lista.html', {
        'catalogo': catalogo, 'q': q, 'tipo_filtro': tipo_filtro, 'status_filtro': status_filtro, 'is_admin': is_admin
    })

@login_required
def catalogo_salvar(request, pk=None):
    """Criação ou Edição manual de um item da REMUME"""
    med = get_object_or_404(Medicamento, pk=pk) if pk else None
    
    if request.method == 'POST':
        codigo_br = request.POST.get('codigo_br', '').strip()
        nome = request.POST.get('nome', '').strip()
        tipo = request.POST.get('tipo')
        forma_farmaceutica = request.POST.get('forma_farmaceutica')
        concentracao = request.POST.get('concentracao', '').strip()
        
        exige_receita_branca = request.POST.get('exige_receita_branca') == 'on'
        exige_receita_controlada = request.POST.get('exige_receita_controlada') == 'on'
        antibiotico = request.POST.get('antibiotico') == 'on'
        ativo = request.POST.get('ativo') == 'on'
        
        if not nome:
            messages.error(request, "O nome do produto é obrigatório.")
        else:
            try:
                if med:
                    med.codigo_br = codigo_br
                    med.nome = nome
                    med.tipo = tipo if tipo else None
                    med.forma_farmaceutica = forma_farmaceutica if forma_farmaceutica else None
                    med.concentracao = concentracao
                    med.exige_receita_branca = exige_receita_branca
                    med.exige_receita_controlada = exige_receita_controlada
                    med.antibiotico = antibiotico
                    med.ativo = ativo
                    med.save()
                    messages.success(request, f'✅ "{nome}" atualizado no catálogo!')
                else:
                    med = Medicamento(
                        codigo_br=codigo_br, nome=nome, tipo=tipo if tipo else None,
                        forma_farmaceutica=forma_farmaceutica if forma_farmaceutica else None,
                        concentracao=concentracao, exige_receita_branca=exige_receita_branca,
                        exige_receita_controlada=exige_receita_controlada, antibiotico=antibiotico, ativo=ativo
                    )
                    med.save()
                    messages.success(request, f'✅ "{nome}" adicionado ao catálogo!')
                return redirect('farmacia:catalogo_lista')
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for campo, erros in e.message_dict.items():
                        for erro in erros: messages.error(request, erro)
                else: messages.error(request, str(e))
                
    tipos = Medicamento.TIPO_CHOICES
    formas = Medicamento.FORMA_CHOICES
    
    return render(request, 'farmacia/catalogo_form.html', {
        'med': med, 'tipos': tipos, 'formas': formas, 'titulo': 'Editar Produto' if med else 'Novo Produto'
    })

# ==============================================================================
# FASE 4: RELATÓRIOS INTELIGENTES
# ==============================================================================

@login_required
def relatorio_faltas(request):
    """Mostra o que mais falta na unidade para a Farmácia solicitar à Central."""
    usf = getattr(request.user.perfil, 'usf_ativa_padrao', None)
    
    ranking_faltas = DemandaReprimida.objects.filter(usf=usf).values(
        'medicamento__nome', 'medicamento__codigo_br', 'medicamento__forma_farmaceutica'
    ).annotate(total_pedidos=Count('id')).order_by('-total_pedidos')
    
    ultimos_registros = DemandaReprimida.objects.filter(usf=usf).select_related(
        'paciente', 'medicamento', 'profissional'
    ).order_by('-data_registro')[:50]
    
    return render(request, 'farmacia/relatorio_faltas.html', {
        'ranking_faltas': ranking_faltas,
        'ultimos_registros': ultimos_registros,
        'usf': usf,
        'hoje': date.today(),
    })