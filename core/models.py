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

class ModuloSistema(models.Model):
    """
    A GRANDE MÁGICA DE ARQUITETURA!
    Controla quais módulos aparecem no Hub e no Menu.
    Substituiu a antiga ConfiguracaoSistema.
    """
    nome = models.CharField('Nome do Módulo (Visível no Menu)', max_length=100)
    slug_app = models.CharField(
        'Nome Interno (App)', max_length=50, unique=True, 
        help_text='Ex exatamente como no código: encaminhamentos, mutirao, vacinas'
    )
    ativo = models.BooleanField('Módulo Ativo', default=False)
    ordem = models.PositiveIntegerField('Ordem de Exibição', default=1)

    class Meta:
        verbose_name = 'Módulo do Sistema'
        verbose_name_plural = 'Módulos do Sistema'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome

class EquipeUSF(models.Model):
    """Vínculo de um profissional com uma USF."""
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name='Profissional', related_name='vinculos_usf'
    )
    usf = models.ForeignKey(
        'USF', on_delete=models.PROTECT, verbose_name='USF', related_name='equipe'
    )
    cargo = models.ForeignKey(
        'Cargo', on_delete=models.PROTECT, verbose_name='Cargo', related_name='profissionais'
    )
    ativo = models.BooleanField(
        'Vínculo ativo', default=True, help_text='Desative ao invés de excluir para preservar o histórico.'
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
    """Micro-área de abrangência de uma USF."""
    usf = models.ForeignKey(
        'USF', on_delete=models.PROTECT, verbose_name='USF', related_name='microareas'
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
        unique_together = ['usf', 'codigo']

    def __str__(self):
        return f'{self.codigo} ({self.usf.nome})'

class Paciente(models.Model):
    """Paciente cadastrado na USF."""
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('I', 'Não informado'),
    ]

    usf = models.ForeignKey('USF', on_delete=models.PROTECT, verbose_name='USF', related_name='pacientes')
    micro_area = models.ForeignKey('MicroArea', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Micro-área', related_name='pacientes')

    nome = models.CharField('Nome completo', max_length=200)
    cpf = models.CharField('CPF', max_length=11, unique=True, null=True, blank=True, validators=[validar_cpf])
    cartao_sus = models.CharField('Cartão SUS (CNS)', max_length=15, unique=True, null=True, blank=True)
    data_nascimento = models.DateField('Data de nascimento', null=True, blank=True)
    sexo = models.CharField('Sexo', max_length=1, choices=SEXO_CHOICES, default='I')

    telefone = models.CharField('Telefone', max_length=11, blank=True)
    endereco = models.CharField('Endereço', max_length=255, blank=True)
    numero = models.CharField('Número', max_length=10, blank=True)

    ativo = models.BooleanField('Ativo', default=True)
    obito = models.BooleanField('Óbito', default=False)
    data_obito = models.DateField('Data do óbito', null=True, blank=True)

    responsavel_familiar = models.BooleanField('É responsável familiar', default=False)
    cpf_responsavel = models.CharField('CPF do responsável familiar', max_length=11, blank=True)
    
    cadastrado_em = models.DateField('Cadastrado na unidade em', default=timezone.now)
    cadastrado_por = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='Cadastrado por', related_name='pacientes_cadastrados')
    
    atualizado = models.BooleanField('Atualizado na última carga', default=True)
    ultima_atualizacao = models.DateTimeField('Última atualização', null=True, blank=True)

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['nome']
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(cpf__isnull=False) | models.Q(cartao_sus__isnull=False)),
                name='paciente_deve_ter_cpf_ou_cns'
            )
        ]

    def __str__(self):
        return f'{self.nome}'
    
    @property
    def idade(self):
        if not self.data_nascimento: return None
        from datetime import date
        hoje = date.today()
        aniversario_passou = ((hoje.month,hoje.day) < (self.data_nascimento.month, self.data_nascimento.day))
        return hoje.year - self.data_nascimento.year - aniversario_passou
    
    @property
    def idade_formatada(self):
        from datetime import date
        if not self.data_nascimento: return "Idade não informada"
        hoje = date.today()
        nasc = self.data_nascimento
        anos = hoje.year - nasc.year
        meses = hoje.month - nasc.month
        dias = hoje.day - nasc.day
        if dias < 0:
            meses -= 1
            dias += 30 
        if meses < 0:
            anos -= 1
            meses += 12
        if anos == 0:
            if meses == 0: return f"{dias} dia{'s' if dias != 1 else ''}"
            else:
                texto = f"{meses} m{'eses' if meses != 1 else 'ês'}"
                if dias > 0: texto += f" e {dias} dia{'s' if dias != 1 else ''}"
                return texto
        else:
            texto = f"{anos} ano{'s' if anos != 1 else ''}"
            if meses > 0: texto += f" e {meses} m{'eses' if meses != 1 else 'ês'}"
            return texto
    
    @property
    def eh_gestante(self):
        if hasattr(self, 'condicoes'):
            return self.condicoes.filter(condicao__codigo__iexact='gestante').exists()
        return False

class CondicaoSaude(models.Model):
    """Condições de saúde cadastradas dinamicamente pelo admin."""
    nome = models.CharField('Nome', max_length=100, unique=True)
    codigo = models.SlugField('Código interno', max_length=50, unique=True)
    icone = models.CharField('Ícone', max_length=10, blank=True)
    afeta_prioridade = models.BooleanField('Afeta prioridade no encaminhamento', default=False)
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
    data_inicio = models.DateField('Data de início')
    data_referencia = models.DateField('Data de referência', null=True, blank=True)
    data_fim = models.DateField('Data de encerramento', null=True, blank=True)
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