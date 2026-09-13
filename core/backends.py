from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User


def limpar_cpf(cpf):
    return ''.join(c for c in cpf if c.isdigit())


class CpfBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        cpf_digitado = limpar_cpf(username or '')
        if not cpf_digitado:
            return None
        try:
            from core.models import PerfilUsuario
            perfil = PerfilUsuario.objects.select_related('user').get(
                cpf=cpf_digitado
            )
            user = perfil.user
        except Exception:
            return None
        if user.check_password(password) and user.is_active:
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


# def limpar_cpf(cpf):
#     # Remove tudo que não for número do CPF digitado.
#     # Ex: '123.456.789-00' vira '12345678900'
#     return ''.join(caractere for caractere in cpf if caractere.isdigit())


# class CpfBackend(BaseBackend):
#     # Essa classe é o nosso backend customizado.
#     # O Django vai chamar o método authenticate()
#     # toda vez que alguém tentar fazer login.

#     def authenticate(self, request, username=None, password=None, **kwargs):
#         # username aqui vai receber o CPF digitado pelo usuário

#         cpf_digitado = limpar_cpf(username or '')

#         # Se depois de limpar não sobrar nenhum número, cancela
#         if not cpf_digitado:
#             return None

#         try:
#             # Importamos aqui dentro para evitar problemas
#             # de importação circular entre arquivos
#             from atendimento.models import PerfilUsuario

#             # Busca o perfil que tem esse CPF
#             # select_related('user') já carrega o User junto,
#             # evitando uma segunda consulta ao banco
#             perfil = PerfilUsuario.objects.select_related('user').get(
#                 cpf=cpf_digitado
#             )
#             user = perfil.user

#         except PerfilUsuario.DoesNotExist:
#             # Se não encontrou nenhum perfil com esse CPF,
#             # retorna None — o Django entende como "login inválido"
#             return None

#         # Verifica se a senha está correta E se o usuário está ativo
#         if user.check_password(password) and user.is_active:
#             return user

#         return None

#     def get_user(self, user_id):
#         # O Django chama esse método para recuperar o usuário
#         # a partir do ID guardado na sessão (após o login)
#         try:
#             return User.objects.get(pk=user_id)
#         except User.DoesNotExist:
#             return None