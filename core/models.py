from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from .validators import validar_cpf


class PerfilUsuario(models.Model):
    """Estende o User padrão com CPF e nível de acesso."""
    NIVEIS = [
        ('admin', 'Administrador'),
        ('funcionario', 'Funcionário'),
        ('usuario', 'Usuário'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil'
    )
    cpf = models.CharField('CPF', max_length=11, unique=True, validators=[validar_cpf])
    nivel = models.CharField(
        'Nível de acesso', max_length=13, choices=NIVEIS, default='usuario'
    )
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Perfil de Profissional'
        verbose_name_plural = 'Perfis de Profissionais'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username}'

    @property
    def is_admin_sistema(self):
        return self.nivel == 'admin' and self.ativo


class USF(models.Model):
    """Unidades de Saúde da Família."""
    nome = models.CharField('Nome da USF', max_length=200, unique=True)
    cnes = models.CharField('CNES', max_length=7, unique=True, null=True, blank=True)
    municipio = models.CharField('Município', max_length=100, default='')
    ativo = models.BooleanField('Ativa', default=True)

    class Meta:
        verbose_name = 'Unidade de Saúde da Família (USF)'
        verbose_name_plural = 'Unidades de Saúde da Família (USFs)'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class TipoAtendimento(models.Model):
    """Tipos de atendimento disponíveis."""
    atendimento = models.CharField('Nome do atendimento', max_length=100, unique=True)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Tipo de Atendimento'
        verbose_name_plural = 'Tipos de Atendimento'
        ordering = ['atendimento']

    def __str__(self):
        return self.atendimento

class Aviso(models.Model):
    """Avisos do mural público da unidade."""
    CATEGORIAS = [
        ('aviso',      'Aviso'),
        ('evento',     'Evento'),
        ('cronograma', 'Cronograma'),
    ]

    titulo = models.CharField('Título', max_length=100)
    mensagem = models.TextField('Mensagem')
    categoria = models.CharField(
        'Categoria', max_length=20, choices=CATEGORIAS, default='aviso'
    )
    data_validade = models.DateField('Válido até')
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Aviso'
        verbose_name_plural = 'Avisos'
        ordering = ['data_validade']

    def __str__(self):
        return f'{self.get_categoria_display()} — {self.titulo}'

class Cargo(models.Model):
    nome = models.CharField('Nome do cargo', max_length=100, unique=True)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        ordering = ['nome']

    def __str__(self):
        return self.nome

class ConfiguracaoSistema(models.Model):
    """
    Configurações gerais do sistema controladas pelo admin.

    Usamos um modelo com uma única linha no banco em vez de
    colocar no settings.py porque assim o admin pode alterar
    sem precisar reiniciar o servidor ou mexer em código.

    O campo 'mutirao_ativo' controla a visibilidade do módulo
    de mutirão no menu — só aparece quando há um evento ativo.
    """
    mutirao_ativo = models.BooleanField(
        'Módulo de mutirão ativo',
        default=False,
        help_text='Quando ativado, o módulo de mutirão aparece '
                  'no menu para todos os usuários. '
                  'Administradores sempre veem todos os módulos.'
    )

    class Meta:
        verbose_name = 'Configuração do Sistema'
        verbose_name_plural = 'Configurações do Sistema'

    def __str__(self):
        return 'Configurações do Sistema'

    @classmethod
    def get(cls):
        """
        Retorna a configuração atual — cria uma com valores
        padrão se ainda não existir. Assim nunca dá erro
        de "objeto não encontrado".
        """
        config, _ = cls.objects.get_or_create(pk=1)
        return config

class EquipeUSF(models.Model):
    """
    Vínculo de um profissional com uma USF.

    Separa o cargo na unidade (ACS, Médico...) do nível de acesso
    ao sistema (PerfilUsuario). Uma enfermeira pode ser cargo
    'Enfermeiro' e ao mesmo tempo ter perfil admin no sistema.
    Um profissional pode ter vínculos em USFs diferentes ao longo
    do tempo — por isso não usamos unique em (user, usf).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,       # não apaga o profissional se ele tiver vínculo
        verbose_name='Profissional',
        related_name='vinculos_usf'
    )
    usf = models.ForeignKey(
        'USF',
        on_delete=models.PROTECT,
        verbose_name='USF',
        related_name='equipe'
    )
    cargo = models.ForeignKey(
        'Cargo',
        on_delete=models.PROTECT,   # não apaga o cargo se tiver profissional vinculado
        verbose_name='Cargo',
        related_name='profissionais')
    
    ativo = models.BooleanField(
        'Vínculo ativo', default=True,
        help_text='Desative ao invés de excluir para preservar o histórico.'
    )
    data_entrada = models.DateField('Data de entrada', null=True, blank=True)
    data_saida = models.DateField('Data de saída', null=True, blank=True)

    class Meta:
        verbose_name = 'Membro da Equipe'
        verbose_name_plural = 'Equipe da USF'
        ordering = ['usf', 'cargo', 'user__first_name']

    def __str__(self):
        nome = self.user.get_full_name() or self.user.username
        return f'{nome} — {self.cargo.nome} ({self.usf})'

class MicroArea(models.Model):
    """
    Micro-área de abrangência de uma USF, geralmente sob a 
    responsabilidade de um Agente Comunitário de Saúde (ACS).
    """
    usf = models.ForeignKey(
        'USF', on_delete=models.PROTECT, 
        verbose_name='USF', related_name='microareas'
    )
    codigo = models.CharField('Código', max_length=10, help_text='Ex: 01, 02, 05A')
    responsavel = models.ForeignKey(
        'EquipeUSF', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Responsável (ACS/TACS)', related_name='microareas_responsavel',
        help_text='Profissional responsável por esta área.'
    )
    ativo = models.BooleanField('Ativa', default=True)

    class Meta:
        verbose_name = 'Micro-área'
        verbose_name_plural = 'Micro-áreas'
        ordering = ['usf', 'codigo']
        unique_together = ['usf', 'codigo'] # Impede ter duas micro-áreas '01' na mesma USF

    def __str__(self):
        return f'{self.codigo} ({self.usf.nome})'

class Paciente(models.Model):
    """
    Paciente cadastrado na USF.

    Identificado por CPF e/ou Cartão SUS (CNS).
    Vinculado a uma USF e a uma micro-área específica,
    o que permitirá o mapa de abrangência na territorialização.
    """
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('I', 'Não informado'),
    ]

   # --- Vínculo institucional ---
    usf = models.ForeignKey(
        'USF', on_delete=models.PROTECT, verbose_name='USF', related_name='pacientes'
    )
    micro_area = models.ForeignKey(
        'MicroArea', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Micro-área', related_name='pacientes'
    )

    # --- Identificação ---
    nome = models.CharField('Nome completo', max_length=200)
    cpf = models.CharField(
        'CPF', max_length=11, unique=True, null=True, blank=True,
        help_text='Somente números, sem pontos ou traços.', validators=[validar_cpf]
    )
    cartao_sus = models.CharField(
        'Cartão SUS (CNS)', max_length=15, unique=True, null=True, blank=True,
        help_text='15 dígitos do Cartão Nacional de Saúde.'
    )
    data_nascimento = models.DateField('Data de nascimento', null=True, blank=True)
    sexo = models.CharField('Sexo', max_length=1, choices=SEXO_CHOICES, default='I')

   # --- Contato e endereço ---
    telefone = models.CharField('Telefone', max_length=11, blank=True)
    endereco = models.CharField('Endereço', max_length=255, blank=True)
    numero = models.CharField('Número', max_length=10, blank=True)

    # --- Controle ---
    ativo = models.BooleanField('Ativo', default=True)

    # --- Óbito ---
    obito = models.BooleanField(
        'Óbito', default=False, help_text='Marque quando o paciente falecer.'
    )
    data_obito = models.DateField(
        'Data do óbito', null=True, blank=True, help_text='Data do falecimento. Preenchimento opcional.'
    )

    # --- Família ---
    responsavel_familiar = models.BooleanField(
        'É responsável familiar', default=False,
        help_text='Marcado automaticamente pela importação do território.'
    )
    cpf_responsavel = models.CharField(
        'CPF do responsável familiar', max_length=11, blank=True,
        help_text='CPF de quem é o responsável pela família. Para o próprio responsável, igual ao seu CPF.'
    )
    
    cadastrado_em = models.DateField(
        'Cadastrado na unidade em', 
        default=timezone.now,
        help_text='Data do cadastro original na USF. Permite retroceder no tempo.'
    )
    cadastrado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Cadastrado por',
        related_name='pacientes_cadastrados'
    )
    # --- Importação ---
    atualizado = models.BooleanField(
        'Atualizado na última carga',
        default=True,
        help_text='Marcado como False antes de cada importação. '
                'Se continuar False após a carga, o paciente não '
                'veio no arquivo e será movido para fora de área.'
    )
    ultima_atualizacao = models.DateTimeField(
        'Última atualização',
        null=True,
        blank=True,
        help_text='Data e hora da última importação que atualizou este paciente.'
)
    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['nome']
        # Garante que ao menos um dos identificadores seja preenchido
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(cpf__isnull=False) |
                    models.Q(cartao_sus__isnull=False)
                ),
                name='paciente_deve_ter_cpf_ou_cns'
            )
        ]

    def __str__(self):
        return f'{self.nome}'
    
    @property
    def idade(self):
        """Calcula a idade atual do paciente."""
        if not self.data_nascimento:
            return None
        from datetime import date
        hoje = date.today()
        aniversario_passou = (
            (hoje.month,hoje.day) <
            (self.data_nascimento.month, self.data_nascimento.day)
        )
        return hoje.year - self.data_nascimento.year - aniversario_passou
    
    
    @property
    def idade_formatada(self):
        """
        Calcula a idade com precisão pediátrica:
        - Menos de 1 mês: Exibe apenas dias (Ex: 29 dias)
        - Menos de 1 ano: Exibe meses e dias (Ex: 2 meses e 15 dias)
        - 1 ano ou mais: Exibe anos e meses (Ex: 1 ano e 3 meses)
        """
        from datetime import date
        
        if not self.data_nascimento:
            return "Idade não informada"
            
        hoje = date.today()
        nasc = self.data_nascimento
        
        anos = hoje.year - nasc.year
        meses = hoje.month - nasc.month
        dias = hoje.day - nasc.day
        
        # Ajuste matemático para meses e dias negativos
        if dias < 0:
            meses -= 1
            # Aproximação de 30 dias para simplificar o cálculo visual
            dias += 30 
        if meses < 0:
            anos -= 1
            meses += 12
            
        # Formatação inteligente solicitada
        if anos == 0:
            if meses == 0:
                return f"{dias} dia{'s' if dias != 1 else ''}"
            else:
                texto = f"{meses} m{'eses' if meses != 1 else 'ês'}"
                if dias > 0:
                    texto += f" e {dias} dia{'s' if dias != 1 else ''}"
                return texto
        else:
            texto = f"{anos} ano{'s' if anos != 1 else ''}"
            if meses > 0:
                texto += f" e {meses} m{'eses' if meses != 1 else 'ês'}"
            return texto
    
    @property
    def eh_gestante(self):
        """
        Verifica nas condições de saúde do paciente se existe alguma com o código 'gestante'.
        Isso conecta perfeitamente com o seu paciente_form.html!
        Verifica nas condições de saúde do paciente se existe alguma com o código 'gestante'.
        """
        if hasattr(self, 'condicoes'):
            # CORREÇÃO AQUI: saltamos da tabela intermediária para a condicao, e depois para o codigo
            return self.condicoes.filter(condicao__codigo__iexact='gestante').exists()
        return False

    # def obter_resumo_encaminhamentos(self):
        #     """
        #     Calcula o impacto de inativar este paciente.
        #     Retorna um dicionário com as guias na fila, disponíveis e concluídas.
        #     """
        #     # Importação local para evitar erro de 'Circular Import'
        #     from encaminhamentos.models import Encaminhamento
    
        #     # 1. Busca os que estão travados na fila
        #     # Usamos select_related('tipo') porque o HTML vai precisar imprimir o nome do tipo
        #     enc_fila = Encaminhamento.objects.filter(
        #         paciente=self,
        #         status__in=['aguardando', 'regulacao', 'upae']
        #     ).select_related('tipo')
    
        #     # 2. Conta quantos estão disponíveis para entrega
        #     disponiveis = Encaminhamento.objects.filter(
        #         paciente=self, 
        #         status='disponivel'
        #     ).count()
    
        #     # 3. Conta o histórico do que já foi resolvido
        #     concluidos = Encaminhamento.objects.filter(
        #         paciente=self, 
        #         status__in=['entregue', 'cancelado', 'unificada']
        #     ).count()
    
        #     # Retorna o "pacote de dados" pronto
        #     return {
        #         'na_fila': enc_fila.count(),
        #         'enc_fila': enc_fila,
        #         'disponiveis': disponiveis,
        #         'concluidos': concluidos,
        #     }

    
class CondicaoSaude(models.Model):
    """
    Condições de saúde cadastradas dinamicamente pelo admin.

    Exemplos: Hipertensão, Diabetes, Gestante, PCD, Asma.

    O campo 'codigo' é usado pela lógica do sistema para
    identificar condições especiais — ex: 'gestante' é verificado
    nas regras de encaminhamento. Os demais códigos são livres.

    O campo 'afeta_prioridade' indica se ter essa condição
    deve sugerir prioridade preferencial no encaminhamento.
    """
    nome = models.CharField(
        'Nome', max_length=100, unique=True,
        help_text='Ex: Hipertensão, Diabetes, Gestante, PCD'
    )
    codigo = models.SlugField(
        'Código interno', max_length=50, unique=True,
        help_text='Identificador único sem espaços. '
                  'Ex: hipertensao, diabetes, gestante, pcd. '
                  'Usado pela lógica do sistema — não altere depois de criado.'
    )
    icone = models.CharField(
        'Ícone', max_length=10, blank=True,
        help_text='Emoji para exibir na lista. Ex: ❤️ 🩸 🤰 ♿'
    )
    afeta_prioridade = models.BooleanField(
        'Afeta prioridade no encaminhamento',
        default=False,
        help_text='Se marcado, o sistema sugere prioridade preferencial '
                  'ao cadastrar encaminhamento para este paciente.'
    )
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Condição de Saúde'
        verbose_name_plural = 'Condições de Saúde'
        ordering = ['nome']

    def __str__(self):
        return f'{self.icone} {self.nome}' if self.icone else self.nome


class PacienteCondicao(models.Model):
    """Vínculo entre um paciente e uma condição de saúde."""
    paciente = models.ForeignKey('Paciente', on_delete=models.CASCADE, verbose_name='Paciente', related_name='condicoes')
    condicao = models.ForeignKey('CondicaoSaude', on_delete=models.PROTECT, verbose_name='Condição', related_name='pacientes')
    data_inicio = models.DateField('Data de início', help_text='Quando a condição foi identificada.')
    data_referencia = models.DateField('Data de referência', null=True, blank=True, help_text='Data relevante para a condição. Para gestante: data prevista do parto. Para outras condições: pode ficar em branco.')
    data_fim = models.DateField('Data de encerramento', null=True, blank=True, help_text='Quando a condição foi resolvida. Deixe em branco se ainda está ativa.')
    observacao = models.TextField('Observação', blank=True)

    class Meta:
        verbose_name = 'Condição do Paciente'
        verbose_name_plural = 'Condições do Paciente'
        ordering = ['-data_inicio']
        constraints = [
            models.UniqueConstraint(
                fields=['paciente', 'condicao'], condition=models.Q(data_fim__isnull=True), name='condicao_ativa_unica_por_paciente'
            )
        ]

    def __str__(self):
        status = 'ativa' if self.ativa else 'encerrada'
        return f'{self.paciente.nome} — {self.condicao.nome} ({status})'

    @property
    def ativa(self):
        return self.data_fim is None

    @property
    def is_gestante(self):
        return self.condicao.codigo == 'gestante' and self.ativa