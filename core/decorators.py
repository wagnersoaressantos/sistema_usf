from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from core.models import EquipeUSF

def admin_required(view_func):
    """Bloqueia o acesso a quem não for Master ou Admin da USF ativa."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        
        perfil = getattr(request.user, 'perfil', None)
        if not perfil:
            messages.warning(request, '⚠ Perfil de utilizador não encontrado.')
            return redirect('core:login')

        # 1. Se for Master Global (ou Superuser do Django), as portas abrem-se magicamente!
        if perfil.is_master or request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        # 2. Se for Admin local, o sistema verifica se ele é chefe NA UNIDADE que está selecionada
        usf_ativa = perfil.usf_ativa_padrao
        if usf_ativa:
            eh_chefe_aqui = EquipeUSF.objects.filter(
                user=request.user,
                usf=usf_ativa,
                is_admin_unidade=True,
                ativo=True
            ).exists()
            
            if eh_chefe_aqui:
                return view_func(request, *args, **kwargs)

        # Se falhou nas verificações, o porteiro barra a entrada
        messages.warning(request, '⚠ Você não tem permissão para acessar essa área.')
        return redirect('core:hub')
        
    return _wrapped_view
    
def master_required(view_func):
    """Permite acesso APENAS aos gestores globais (Master)."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
            
        perfil = getattr(request.user, 'perfil', None)
        if perfil and (perfil.is_master or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
            
        messages.warning(request, '⚠ Acesso restrito à Gestão Municipal.')
        return redirect('core:hub')
        
    return _wrapped_view