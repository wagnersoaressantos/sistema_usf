from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.apps import apps
from django.core.paginator import Paginator

from core.models import Paciente, EquipeUSF, PacienteCondicao
from territorializacao.models import FamiliaScore

@login_required
def hub_pacientes(request):
    """
    O Cérebro da Busca de Pacientes.
    Lê o que o utilizador digitou e procura na base de dados.
    """
    # 1. Descobrir a USF ativa do utilizador
    perfil = getattr(request.user, 'perfil', None)
    usf = perfil.usf_ativa_padrao if perfil else None

    if not usf:
        vinculo = EquipeUSF.objects.filter(user=request.user, ativo=True).first()
        usf = vinculo.usf if vinculo else None

    q = request.GET.get('q', '')
    
    # 2. Buscar Pacientes filtrando pela USF e pelo termo
    if usf:
        pacientes_query = Paciente.objects.filter(usf=usf).select_related('micro_area')
        if q:
            pacientes_query = pacientes_query.filter(
                Q(nome__icontains=q) | 
                Q(cpf__icontains=q) | 
                Q(cartao_sus__icontains=q)
            )
    else:
        pacientes_query = Paciente.objects.none()

    # 3. Paginação para não sobrecarregar o ecrã
    paginator = Paginator(pacientes_query.order_by('nome'), 20)
    page = request.GET.get('page')
    pacientes = paginator.get_page(page)

    return render(request, 'pacientes/hub.html', {
        'pacientes': pacientes,
        'q': q,
        'usf': usf
    })

@login_required
def perfil_paciente(request, pk):
    """
    O Cérebro do Prontuário 360º.
    Junta Clínica, Território e Fila de Espera num único lugar.
    """
    usf = getattr(request.user.perfil, 'usf_ativa_padrao', None)
    paciente = get_object_or_404(Paciente, pk=pk, usf=usf)

    # 1. Condições de Saúde (Marcadores e Doenças)
    condicoes_ativas = PacienteCondicao.objects.filter(
        paciente=paciente, data_fim__isnull=True
    ).select_related('condicao')

    # 2. Score de Risco Familiar (Integração com Território)
    familia = None
    if paciente.cpf_responsavel:
        familia = FamiliaScore.objects.filter(cpf_responsavel=paciente.cpf_responsavel, usf=usf).first()

    # 3. Encaminhamentos (Integração com Regulação)
    encaminhamentos = []
    if apps.is_installed('encaminhamentos'):
        Encaminhamento = apps.get_model('encaminhamentos', 'Encaminhamento')
        encaminhamentos = Encaminhamento.objects.filter(paciente=paciente).select_related('tipo').order_by('-data_solicitacao')

    # 4. Saber quais módulos estão ligados
    from core.models import ModuloSistema
    modulos_ativos = list(ModuloSistema.objects.filter(ativo=True).values_list('slug_app', flat=True))

    perfil = getattr(request.user, 'perfil', None)
    is_master = perfil.is_master if perfil else False
    is_admin_unidade = False
    
    if not is_master and usf:
        is_admin_unidade = EquipeUSF.objects.filter(user=request.user, usf=usf, is_admin_unidade=True, ativo=True).exists()

    context = {
        'paciente': paciente,
        'condicoes_ativas': condicoes_ativas,
        'familia': familia,
        'encaminhamentos': encaminhamentos,
        'modulos_ativos': modulos_ativos,
        'is_master': is_master,
        'is_admin_unidade': is_admin_unidade,
    }
    return render(request, 'pacientes/perfil.html', context)