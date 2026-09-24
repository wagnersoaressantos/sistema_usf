from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q

from core.decorators import admin_required
from core.models import EquipeUSF, Paciente, USF
from .models import ConfigCota, ConfigCotaSubcategoria, Encaminhamento, HistoricoEncaminhamento, TipoEncaminhamento, Subcategoria

# --- FUNÇÃO AUXILIAR ---
def obter_usf_usuario(user):
    """Retorna a USF do usuário logado baseado na equipe."""
    vinculo = EquipeUSF.objects.filter(user=user, ativo=True).select_related('usf').first()
    return vinculo.usf if vinculo else None

# ==============================================================================
# VIEWS DO SISTEMA DE ENCAMINHAMENTOS
# ==============================================================================

@login_required
def inicio(request):
    """
    Dashboard principal do módulo de encaminhamentos.
    Mostra os cards de resumo e os atalhos.
    """
    usf = obter_usf_usuario(request.user)
    if not usf:
        messages.error(request, 'Você precisa estar vinculado a uma USF para acessar a Regulação.')
        return redirect('core:hub')

    # Contagens Rápidas para os Cards
    fila_espera = Encaminhamento.objects.filter(usf=usf, status__in=['aguardando', 'regulacao', 'upae']).count()
    disponiveis = Encaminhamento.objects.filter(usf=usf, status='disponivel').count()
    concluidos = Encaminhamento.objects.filter(usf=usf, status__in=['entregue', 'unificada']).count()
    
    # Busca as subcategorias (Exames, Consultas) para mostrar na tela
    subcategorias = Subcategoria.objects.filter(ativo=True).annotate(
        total_fila=Count('tipos__encaminhamentos', filter=Q(tipos__encaminhamentos__status__in=['aguardando', 'regulacao', 'upae'], tipos__encaminhamentos__usf=usf))
    ).order_by('nome')

    context = {
        'fila_espera': fila_espera,
        'disponiveis': disponiveis,
        'concluidos': concluidos,
        'subcategorias': subcategorias,
        'usf': usf,
    }
    return render(request, 'encaminhamentos/inicio.html', context)


@login_required
def lista_encaminhamentos(request):
    """
    Mostra a fila de espera atual (Aguardando ou Em Regulação).
    """
    usf = obter_usf_usuario(request.user)
    
    # --- NOVO: Captura o filtro da URL (Ex: ?tipo=5) ---
    tipo_filtro = request.GET.get('tipo', '')
    
    encaminhamentos = Encaminhamento.objects.filter(
        usf=usf, 
        status__in=['aguardando', 'regulacao', 'upae']
    ).select_related('paciente', 'tipo__subcategoria').order_by('-prioridade', 'data_status_atual')

    # Aplica o filtro se o usuário escolheu uma fila específica
    if tipo_filtro:
        encaminhamentos = encaminhamentos.filter(tipo_id=tipo_filtro)
        
    # Pega apenas os tipos que têm gente na fila para mostrar no Select
    tipos_na_fila = TipoEncaminhamento.objects.filter(
        encaminhamentos__usf=usf, 
        encaminhamentos__status__in=['aguardando', 'regulacao', 'upae']
    ).distinct().order_by('nome')

    return render(request, 'encaminhamentos/lista.html', {
        'encaminhamentos': encaminhamentos,
        'tipos_na_fila': tipos_na_fila,
        'tipo_filtro': int(tipo_filtro) if tipo_filtro else '',
        'titulo_pagina': 'Fila de Espera',
    })


@login_required
def concluidos(request):
    """
    Mostra o histórico de guias já entregues ou canceladas.
    """
    usf = obter_usf_usuario(request.user)
    
    encaminhamentos = Encaminhamento.objects.filter(
        usf=usf, 
        status__in=['entregue', 'cancelado', 'unificada']
    ).select_related('paciente', 'tipo').order_by('-data_solicitacao')[:200] # Limita aos 200 mais recentes

    return render(request, 'encaminhamentos/concluidos.html', {
        'encaminhamentos': encaminhamentos,
    })


@login_required
def cadastrar(request):
    """
    Cria uma nova guia de encaminhamento.
    """
    usf = obter_usf_usuario(request.user)
    
    if request.method == 'POST':
        paciente_id = request.POST.get('paciente')
        tipo_id = request.POST.get('tipo')
        motivo = request.POST.get('motivo', '')
        observacao = request.POST.get('observacao', '')
        prioridade = request.POST.get('prioridade', 1)
        data_solicitacao_str = request.POST.get('data_solicitacao')
        
        if not paciente_id or not tipo_id:
            messages.error(request, 'Selecione o Paciente e o Procedimento.')
        else:
            paciente = get_object_or_404(Paciente, pk=paciente_id, usf=usf)
            tipo = get_object_or_404(TipoEncaminhamento, pk=tipo_id)
            
            # Converte a data digitada ou usa hoje
            data_solicitacao = timezone.now().date()
            if data_solicitacao_str:
                from datetime import datetime
                try:
                    data_solicitacao = datetime.strptime(data_solicitacao_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            nova_guia = Encaminhamento.objects.create(
                paciente=paciente,
                usf=usf,
                tipo=tipo,
                motivo=motivo,
                observacao=observacao,
                prioridade=prioridade,
                data_solicitacao=data_solicitacao,
                data_status_atual=timezone.now().date(),
                solicitado_por=request.user
            )

            # MÁGICA: Grava o marco zero no histórico!
            HistoricoEncaminhamento.objects.create(
                encaminhamento=nova_guia,
                status='aguardando',
                observacao=f"Guia solicitada. {observacao}",
                registrado_por=request.user
            )
            
            messages.success(request, f'Encaminhamento para {paciente.nome} criado com sucesso!')
            return redirect('encaminhamentos:inicio')

    # Para o GET, manda as listas para popular o Select
    pacientes = Paciente.objects.filter(usf=usf, ativo=True).order_by('nome')
    tipos = TipoEncaminhamento.objects.filter(ativo=True).select_related('subcategoria').order_by('subcategoria__nome', 'nome')

    return render(request, 'encaminhamentos/cadastrar.html', {
        'pacientes': pacientes,
        'tipos': tipos,
    })


@login_required
def detalhe(request, pk):
    """
    Mostra os detalhes de um encaminhamento e permite mudar o status.
    """
    usf = obter_usf_usuario(request.user)
    encaminhamento = get_object_or_404(Encaminhamento, pk=pk, usf=usf)
    
    if request.method == 'POST':
        novo_status = request.POST.get('status')
        nova_observacao = request.POST.get('observacao', '')
        
        if novo_status in dict(Encaminhamento.STATUS_CHOICES).keys():
            # Atualiza o relógio apenas se o status mudou!
            if encaminhamento.status != novo_status:
                encaminhamento.data_status_atual = timezone.now().date()
            
            encaminhamento.status = novo_status
            encaminhamento.observacao = nova_observacao
            encaminhamento.save()

            # MÁGICA: Grava este passo no livro de histórico!
            HistoricoEncaminhamento.objects.create(
                encaminhamento=encaminhamento,
                status=novo_status,
                observacao=nova_observacao,
                registrado_por=request.user
            )

            messages.success(request, 'Guia atualizada com sucesso!')
            return redirect('encaminhamentos:detalhe', pk=pk)

    return render(request, 'encaminhamentos/detalhe.html', {
        'encaminhamento': encaminhamento,
        'status_choices': Encaminhamento.STATUS_CHOICES,
    })

# ==============================================================================
# 🚀 FASE 7: ADMINISTRAÇÃO DA REGULAÇÃO (LINGUAGEM UBÍQUA)
# ==============================================================================

@admin_required
def admin_tipos_enc(request):
    """Lista todos os Grupos (Subcategorias) e as Especialidades (Tipos) atreladas a eles."""
    # O prefetch_related carrega todas as especialidades de cada categoria num único comando rápido
    categorias = Subcategoria.objects.prefetch_related('tipos').all().order_by('nome')
    return render(request, 'encaminhamentos/admin/especialidades.html', {'categorias': categorias})

@admin_required
def admin_categoria_salvar(request, pk=None):
    """Cria ou edita um Grupo Principal (Subcategoria no DB)."""
    categoria = get_object_or_404(Subcategoria, pk=pk) if pk else None
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        cota_padrao = int(request.POST.get('cota_padrao', 0))
        ativo = request.POST.get('ativo') == 'on'
        
        if not nome:
            messages.error(request, 'O nome da Categoria/Grupo é obrigatório.')
        else:
            if categoria:
                categoria.nome = nome
                categoria.cota_padrao = cota_padrao
                categoria.ativo = ativo
                categoria.save()
                messages.success(request, f'Grupo "{nome}" atualizado com sucesso!')
            else:
                Subcategoria.objects.create(nome=nome, cota_padrao=cota_padrao, ativo=ativo)
                messages.success(request, f'Grupo "{nome}" criado com sucesso!')
            return redirect('encaminhamentos:admin_tipos_enc')
            
    return render(request, 'encaminhamentos/admin/categoria_form.html', {
        'categoria': categoria,
        'titulo': 'Editar Grupo/Categoria' if categoria else 'Novo Grupo Principal',
        'acao': 'Salvar Grupo' if categoria else 'Criar Grupo'
    })

@admin_required
def admin_especialidade_salvar(request, pk=None):
    """Cria ou edita uma Especialidade (TipoEncaminhamento no DB)."""
    especialidade = get_object_or_404(TipoEncaminhamento, pk=pk) if pk else None
    categorias = Subcategoria.objects.filter(ativo=True).order_by('nome')
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        subcategoria_id = request.POST.get('subcategoria')
        cota_padrao = int(request.POST.get('cota_padrao', 0))
        idade_min = request.POST.get('idade_minima')
        idade_max = request.POST.get('idade_maxima')
        ativo = request.POST.get('ativo') == 'on'
        
        if not nome or not subcategoria_id:
            messages.error(request, 'O Nome e o Grupo Principal são obrigatórios.')
        else:
            dados = {
                'nome': nome,
                'subcategoria_id': subcategoria_id,
                'cota_padrao': cota_padrao,
                'idade_minima': int(idade_min) if idade_min else None,
                'idade_maxima': int(idade_max) if idade_max else None,
                'ativo': ativo
            }
            if especialidade:
                for k, v in dados.items():
                    setattr(especialidade, k, v)
                especialidade.save()
                messages.success(request, f'Especialidade "{nome}" atualizada!')
            else:
                TipoEncaminhamento.objects.create(**dados)
                messages.success(request, f'Especialidade "{nome}" criada!')
            return redirect('encaminhamentos:admin_tipos_enc')
            
    return render(request, 'encaminhamentos/admin/especialidade_form.html', {
        'especialidade': especialidade,
        'categorias': categorias,
        'titulo': 'Editar Especialidade / Exame' if especialidade else 'Nova Especialidade',
        'acao': 'Salvar Especialidade' if especialidade else 'Criar Especialidade'
    })

@admin_required
def admin_cotas(request):
    """Painel Geral de Cotas (Limites por USF)."""
    # Exibe USFs que têm "mordomias" ou "cortes" nas cotas padrão
    cotas_especialidades = ConfigCota.objects.select_related('usf', 'tipo__subcategoria').all()
    cotas_categorias = ConfigCotaSubcategoria.objects.select_related('usf', 'subcategoria').all()
    
    return render(request, 'encaminhamentos/admin/cotas.html', {
        'cotas_especialidades': cotas_especialidades,
        'cotas_categorias': cotas_categorias
    })