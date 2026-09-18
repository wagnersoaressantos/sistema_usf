from django.conf import settings
from django.utils import timezone

def sistema_info(request):
    """
    Injeta informações do sistema em todas as telas HTML automaticamente.
    """
    # Adicionámos o import do modelo USF
    from core.models import Aviso, EquipeUSF, ModuloSistema, USF

    hoje = timezone.now().date()

    avisos = Aviso.objects.filter(
        ativo=True,
        data_validade__gte=hoje
    ).order_by('data_validade')

    modulos_ativos = list(ModuloSistema.objects.filter(ativo=True).values_list('slug_app', flat=True))

    # --- 🚀 MÁGICA DA ALTERNÂNCIA DE USFs E MULTI-TENANCY ---
    usuario_usf = None
    usfs_permitidas = []
    is_master = False
    is_admin_unidade = False

    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        perfil = request.user.perfil
        is_master = perfil.is_master

        # 1. Lista de Postos Permitidos
        if is_master:
            # O Supremo Gestor vê TODAS as USFs do município
            usfs_permitidas = list(USF.objects.filter(ativo=True).order_by('nome'))
        else:
            # O profissional comum vê APENAS as USFs onde tem contrato (vínculo)
            vinculos = EquipeUSF.objects.filter(user=request.user, ativo=True).select_related('usf')
            usfs_permitidas = [v.usf for v in vinculos]

        # 2. Descobre qual a USF ativa HOJE
        if perfil.usf_ativa_padrao and perfil.usf_ativa_padrao in usfs_permitidas:
            usuario_usf = perfil.usf_ativa_padrao
        elif usfs_permitidas:
            # Se não escolheu nenhuma ainda, pega a primeira e salva na memória!
            usuario_usf = usfs_permitidas[0]
            perfil.usf_ativa_padrao = usuario_usf
            perfil.save()

        # 3. Descobre se ele é o "Chefe" (Admin) nesta USF atual
        if is_master:
            is_admin_unidade = True
        elif usuario_usf:
            vinculo_atual = EquipeUSF.objects.filter(user=request.user, usf=usuario_usf, ativo=True).first()
            if vinculo_atual:
                is_admin_unidade = vinculo_atual.is_admin_unidade

    return {
        'sistema':          settings.SISTEMA,
        'ano_atual':        hoje.year,
        'avisos':           avisos,
        'modulos_ativos':   modulos_ativos,
        
        # Variáveis novas enviadas para os ecrãs (Templates)
        'usuario_usf':      usuario_usf,
        'usfs_permitidas':  usfs_permitidas,
        'is_master':        is_master,
        'is_admin_unidade': is_admin_unidade,
    }