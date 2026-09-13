import getpass
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import PerfilUsuario
from core.validators import validar_cpf
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = 'Cria um superusuário completo, já com PerfilUsuario (CPF) atrelado.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('=== Criação de Administrador do Sistema ==='))

        # 1. Coleta e valida o Nome
        nome = input('Nome: ').strip()
        while not nome:
            self.stdout.write(self.style.ERROR('O nome é obrigatório.'))
            nome = input('Nome: ').strip()

        sobrenome = input('Sobrenome: ').strip()

        # 2. Coleta e valida o CPF
        cpf_valido = False
        cpf_limpo = ''
        while not cpf_valido:
            cpf_raw = input('CPF (apenas números): ').strip()
            cpf_limpo = ''.join(c for c in cpf_raw if c.isdigit())
            
            try:
                validar_cpf(cpf_limpo)
                # Verifica se já existe no banco
                if PerfilUsuario.objects.filter(cpf=cpf_limpo).exists():
                    self.stdout.write(self.style.ERROR('Este CPF já está cadastrado no sistema.'))
                else:
                    cpf_valido = True
            except ValidationError as e:
                self.stdout.write(self.style.ERROR(e.message))

        # 3. Coleta e valida a Senha
        senha_valida = False
        senha = ''
        while not senha_valida:
            senha = getpass.getpass('Senha: ')
            senha2 = getpass.getpass('Confirme a Senha: ')
            
            if senha != senha2:
                self.stdout.write(self.style.ERROR('As senhas não coincidem. Tente novamente.'))
            elif len(senha) < 6:
                self.stdout.write(self.style.ERROR('A senha deve ter pelo menos 6 caracteres.'))
            else:
                senha_valida = True

        # 4. Criação no Banco de Dados
        try:
            # Cria o usuário padrão do Django com privilégios máximos
            username_gerado = f'user_{cpf_limpo}'
            user = User.objects.create_superuser(
                username=username_gerado,
                email='', # Opcional, deixamos vazio
                password=senha,
                first_name=nome,
                last_name=sobrenome
            )

            # Cria o perfil do sistema atrelado ao usuário
            PerfilUsuario.objects.create(
                user=user,
                cpf=cpf_limpo,
                nivel='admin',
                ativo=True
            )

            self.stdout.write(self.style.SUCCESS(f'\n✅ Superusuário {nome} (CPF: {cpf_limpo}) criado com sucesso!'))
            self.stdout.write(self.style.SUCCESS('Você já pode fazer login no sistema.'))

        except Exception as e:
            raise CommandError(f'Erro ao criar usuário: {str(e)}')