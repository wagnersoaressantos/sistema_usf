from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from django.apps import apps

# Importando o que precisamos do "Core"
from core.models import Paciente

# Importando a Inteligência Geográfica
from territorializacao.models import FamiliaScore

@login_required
def hub_pacientes(request):
    """
    Tela central de pesquisa. Permite ao rececionista ou médico
    pesquisar um paciente por Nome, CPF ou Cartão SUS.
    """
    # 1. Mágica do Multi-tenancy: Descobre em qual USF o usuário está agora
    usf = request.user.perfil.usf_ativa_padrao
    
    # 2. Pega a palavra que o usuário digitou na barra de busca (se houver)
    q = request.GET.get('q', '').strip()
    
    # 3. Busca apenas os pacientes ativos e VIVOS desta unidade
    pacientes_query = Paciente.objects.filter(usf=usf, ativo=True, obito=False)
    
    # Se ele digitou algo, filtramos! O "Q" permite buscar com "OU" (Nome OU CPF OU CNS)
    if q:
        pacientes_query = pacientes_query.filter(
            Q(nome__icontains=q) | 
            Q(cpf__icontains=q) | 
            Q(cartao_sus__icontains=q)
        )
    
    # Ordena alfabeticamente
    pacientes_query = pacientes_query.order_by('nome')
    
    # 4. Paginação: Não queremos carregar 5.000 pacientes de uma vez!
    # Mostraremos apenas 30 por página para o sistema ser rápido como um foguete.
    paginador = Paginator(pacientes_query, 30)
    pagina = request.GET.get('page', 1)
    pacientes_paginados = paginador.get_page(pagina)

    return render(request, 'pacientes/hub.html', {
        'pacientes': pacientes_paginados,
        'q': q,
        'usf': usf
    })


@login_required
def perfil_paciente(request, pk):
    """
    O PRONTUÁRIO 360º.
    Reúne todas as informações do paciente num único lugar.
    """
    usf = request.user.perfil.usf_ativa_padrao
    
    # 1. Busca a Base: Os dados do Paciente
    paciente = get_object_or_404(Paciente, pk=pk, usf=usf)
    
    # 2. Busca as Condições (As Tags Coloridas de Doenças Ativas)
    condicoes_ativas = paciente.condicoes.filter(data_fim__isnull=True).select_related('condicao')
    
    # 3. Busca o Contexto Social (Família e Score de Coelho e Savassi)
    # EXPLICAÇÃO: Usamos o "cpf_responsavel" dele para achar a gaveta da família!
    familia = None
    if paciente.cpf_responsavel:
        familia = FamiliaScore.objects.filter(usf=usf, cpf_responsavel=paciente.cpf_responsavel).first()
        
    # 4. Busca o Histórico Médico (Encaminhamentos)
    # EXPLICAÇÃO: Só busca se a App de Encaminhamentos estiver ligada!
    encaminhamentos = []
    if apps.is_installed('encaminhamentos'):
        Encaminhamento = apps.get_model('encaminhamentos', 'Encaminhamento')
        # Pega todas as guias dele, da mais recente para a mais antiga
        encaminhamentos = Encaminhamento.objects.filter(paciente=paciente).select_related('tipo__subcategoria').order_by('-data_solicitacao')
        
    context = {
        'paciente': paciente,
        'condicoes_ativas': condicoes_ativas,
        'familia': familia,
        'encaminhamentos': encaminhamentos,
    }
    return render(request, 'pacientes/perfil.html', context)