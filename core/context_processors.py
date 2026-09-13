from django.conf import settings
from django.utils import timezone


def sistema_info(request):
    """
    Injeta informações do sistema em todos os templates.

    Além das infos básicas, injeta:
    - avisos: avisos ativos da unidade
    - mutirao_ativo: se o módulo de mutirão está visível no menu
    - usuario_usf: a USF do usuário logado (para filtros)

    O Django chama essa função em toda requisição automaticamente
    porque está registrada em TEMPLATES > context_processors
    no settings.py.
    """
    from core.models import Aviso, ConfiguracaoSistema, EquipeUSF

    hoje = timezone.now().date()

    # Busca avisos ativos dentro da validade
    avisos = Aviso.objects.filter(
        ativo=True,
        data_validade__gte=hoje
    ).order_by('data_validade')

    # Busca configuração do sistema com valores padrão seguros
    # get_or_create garante que nunca vai dar erro se não existir
    config = ConfiguracaoSistema.get()

    # Descobre a USF do usuário logado via vínculo na equipe
    # Usado para filtrar dados por unidade em todo o sistema
    usuario_usf = None
    if request.user.is_authenticated:
        vinculo = EquipeUSF.objects.filter(
            user=request.user,
            ativo=True
        ).select_related('usf').first()
        if vinculo:
            usuario_usf = vinculo.usf

    return {
        'sistema':       settings.SISTEMA,
        'ano_atual':     timezone.now().year,
        'avisos':        avisos,
        # True se admin ativou o mutirão OU se o usuário é admin
        # Admin sempre vê todos os módulos
        'mutirao_ativo': (
            config.mutirao_ativo or
            (request.user.is_authenticated and
             hasattr(request.user, 'perfil') and
             request.user.perfil.is_admin_sistema)
        ),
        'usuario_usf':   usuario_usf,
    }