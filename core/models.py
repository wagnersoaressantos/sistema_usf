from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User

from config import settings
from .validators import validar_cpf

class PerfilUsuario(models.Model):
    """
    A Pessoa física. Login único no sistema.
    Aqui não guardamos mais se ele é 'Admin' ou 'Comum', pois isso 
    depende de qual posto de saúde ele está a trabalhar hoje.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    cpf = models.CharField('CPF', max_length=11, unique=True, validators=[validar_cpf])
    
    # --- PODER GLOBAL (O SUPREMO) ---
    # Se is_master for True, este utilizador é da Secretaria de Saúde ou TI.
    # Ele tem acesso a todas as USFs, pode criar novas USFs e ligar/desligar módulos.
    is_master = models.BooleanField('Gestor Municipal (Master)', default=False, help_text='Tem acesso a todas as USFs e configurações globais.')
    
    # --- MEMÓRIA DO SISTEMA ---
    # Se o médico trabalha em 2 postos, ele escolhe no topo da tela em qual está hoje.
    # Guardamos essa escolha aqui para que, ao mudar de página, o sistema não esqueça onde ele está.
    usf_ativa_padrao = models.ForeignKey('USF', on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios_logados')
    
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Perfil do Utilizador'
        verbose_name_plural = 'Perfis dos Utilizadores'

    def __str__(self):
        return f'{self.user.get_full_name()} ({self.cpf})'


class EquipeUSF(models.Model):
    """
    O Vínculo de Trabalho (O Chapéu). Um utilizador pode ter vários.
    Aqui é onde definimos o PODER LOCAL.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Profissional', related_name='vinculos_equipe')
    usf = models.ForeignKey('USF', on_delete=models.CASCADE, verbose_name='USF', related_name='equipe')
    cargo = models.ForeignKey('Cargo', on_delete=models.PROTECT, verbose_name='Cargo')
    
    # --- PODER LOCAL (O COORDENADOR DO POSTO) ---
    # Se isto for True, o profissional é 'Admin' APENAS DESTA USF.
    # Ele poderá adicionar membros, editar pacientes e ver todos os relatórios DAQUI.
    # Se ele for para outra USF onde isto seja False, ele será apenas um profissional comum lá.
    is_admin_unidade = models.BooleanField('Administrador desta Unidade', default=False, help_text='Pode gerir a equipa apenas nesta USF.')
    
    data_entrada = models.DateField('Data de entrada', null=True, blank=True)
    data_saida = models.DateField('Data de saída', null=True, blank=True)
    ativo = models.BooleanField('Vínculo Ativo', default=True)

    class Meta:
        verbose_name = 'Vínculo na USF'
        verbose_name_plural = 'Equipa das USFs'
        unique_together = ['user', 'usf'] # A mesma pessoa não pode ter 2 vínculos na MESMA USF simultaneamente.

    def __str__(self):
        tipo = " (Admin)" if self.is_admin_unidade else ""
        return f'{self.user.get_full_name()} - {self.cargo.nome} na {self.usf.nome}{tipo}'

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

    def save(self, *args, **kwargs):
        """MÁGICA: Se ele for o Responsável Familiar, auto-preenche o CPF do Responsável com o próprio CPF dele!"""
        if self.responsavel_familiar and self.cpf:
            self.cpf_responsavel = self.cpf
        super().save(*args, **kwargs)
    
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

class HistoricoFamiliar(models.Model):
    GRAUS = [
        ('pai_mae', 'Pai / Mãe'),
        ('avo', 'Avô / Avó'),
        ('irmao', 'Irmão / Irmã'),
        ('outro', 'Outro'),
    ]
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='historico_familiar')
    condicao = models.CharField('Condição/Doença', max_length=150)
    grau_parentesco = models.CharField('Grau de Parentesco', max_length=20, choices=GRAUS)
    observacao = models.CharField('Observação', max_length=255, blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'Histórico Familiar'
        verbose_name_plural = 'Históricos Familiares'

    def __str__(self):
        return f'{self.paciente.nome} - {self.condicao} ({self.get_grau_parentesco_display()})'