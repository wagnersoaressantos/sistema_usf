from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """
    Decorator que protege views para acesso apenas de admins do sistema.

    Como funciona:
    1. O usuário precisa estar logado (is_authenticated)
    2. O usuário precisa ter um perfil (PerfilUsuario)
    3. O perfil precisa ter nivel='admin' E ativo=True

    Se qualquer condição falhar, redireciona para a listagem
    com uma mensagem de erro.

    Uso:
    @admin_required
    def minha_view(request):
        ...
    """
    @wraps(view_func)
    # @wraps preserva o nome e documentação da função original.
    # Sem isso, todas as views decoradas teriam o nome 'wrapper'.
    def wrapper(request, *args, **kwargs):

        # Verifica se está logado
        if not request.user.is_authenticated:
            return redirect('core:login')

        # Verifica se tem perfil e se é admin ativo
        try:
            perfil = request.user.perfil
            if not perfil.is_admin_sistema:
                messages.error(request, 'Você não tem permissão para acessar essa área.')
                return redirect('core:hub')
        except Exception:
            # Se não tiver perfil, não tem acesso
            messages.error(request, 'Você não tem permissão para acessar essa área.')
            return redirect('core:hub')

        # Tudo certo — executa a view normalmente
        return view_func(request, *args, **kwargs)

    return wrapper