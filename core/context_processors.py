from django.conf import settings
from django.utils import timezone

def sistema_info(request):
    """
    Injeta informações do sistema em todas as telas HTML automaticamente.
    O Django chama essa função em toda requisição porque ela está 
    registrada em TEMPLATES > context_processors no settings.py.
    """
    # Importamos aqui dentro para evitar "Dependência Circular"
    from core.models import Aviso, EquipeUSF, ModuloSistema

    hoje = timezone.now().date()

    # 1. Busca avisos ativos dentro da validade
    avisos = Aviso.objects.filter(
        ativo=True,
        data_validade__gte=hoje
    ).order_by('data_validade')

    # 2. Descobre a USF do usuário logado via vínculo na equipe
    usuario_usf = None
    if request.user.is_authenticated:
        vinculo = EquipeUSF.objects.filter(
            user=request.user,
            ativo=True
        ).select_related('usf').first()
        if vinculo:
            usuario_usf = vinculo.usf

    # 3. MÁGICA DOS MÓDULOS (Substituiu a ConfiguracaoSistema)
    # Lista com o nome dos módulos ativados no painel (Ex: ['encaminhamentos', 'mutirao'])
    modulos_ativos = list(ModuloSistema.objects.filter(ativo=True).values_list('slug_app', flat=True))

    return {
        'sistema':        settings.SISTEMA,
        'ano_atual':      hoje.year,
        'avisos':         avisos,
        'usuario_usf':    usuario_usf,
        'modulos_ativos': modulos_ativos, # Ajuda o Menu a esconder ou mostrar botões!
    }