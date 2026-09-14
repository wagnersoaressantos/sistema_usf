from django.db import models
from django.conf import settings
from core.models import Paciente, USF, CondicaoSaude

# =============================================================================
# ARQUITETURA AVANÇADA DE REGULAÇÃO E COTAS
# =============================================================================

class Subcategoria(models.Model):
    """
    Classificação macro do encaminhamento.
    Ex: 'Consulta Especializada', 'Exame de Imagem', 'Exame Laboratorial'.
    """
    nome = models.CharField('Subcategoria', max_length=100, unique=True)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Subcategoria'
        verbose_name_plural = 'Subcategorias'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class TipoEncaminhamento(models.Model):
    """
    O procedimento ou especialidade específica.
    Ex: 'Cardiologia', 'Raio-X de Tórax', 'Ultrassom Obstétrica'.
    """
    nome = models.CharField('Especialidade/Procedimento', max_length=150)
    subcategoria = models.ForeignKey(
        Subcategoria, on_delete=models.PROTECT, related_name='tipos'
    )
    cota_padrao = models.PositiveIntegerField(
        'Cota Mensal Padrão', default=0,
        help_text='Quantas vagas a unidade recebe por mês para este procedimento.'
    )
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Tipo de Encaminhamento'
        verbose_name_plural = 'Tipos de Encaminhamento'
        ordering = ['subcategoria', 'nome']

    def __str__(self):
        return f'{self.nome} ({self.subcategoria.nome})'


class ConfigCota(models.Model):
    """
    Permite definir uma cota específica para uma USF diferente do padrão.
    Ex: Se a USF Centro tem mais médicos, pode ter uma cota maior de USG.
    """
    usf = models.ForeignKey(USF, on_delete=models.CASCADE, related_name='cotas_extras')
    tipo = models.ForeignKey(TipoEncaminhamento, on_delete=models.CASCADE, related_name='configuracoes_cotas')
    quantidade = models.PositiveIntegerField('Quantidade Específica da USF')

    class Meta:
        verbose_name = 'Configuração de Cota por USF'
        verbose_name_plural = 'Configurações de Cotas por USF'
        unique_together = ['usf', 'tipo']

    def __str__(self):
        return f'{self.tipo.nome} na {self.usf.nome} = {self.quantidade}'


class RegraCondicao(models.Model):
    """
    A GRANDE INTELIGÊNCIA DO SISTEMA!
    Aqui definimos que se o Paciente tem a Doença X, ele tem privilégios
    para o Exame/Consulta Y.
    """
    tipo = models.ForeignKey(TipoEncaminhamento, on_delete=models.CASCADE, related_name='regras')
    condicao = models.ForeignKey(CondicaoSaude, on_delete=models.CASCADE, related_name='regras_encaminhamento')
    fura_fila = models.BooleanField(
        'Prioridade Máxima', default=False,
        help_text='Passa automaticamente para o topo da fila.'
    )
    isento_cota = models.BooleanField(
        'Isento de Cota', default=False,
        help_text='Não desconta da cota mensal da unidade (Ex: Gestante não gasta cota de USG).'
    )

    class Meta:
        verbose_name = 'Regra Especial por Condição'
        verbose_name_plural = 'Regras Especiais por Condição'
        unique_together = ['tipo', 'condicao']

    def __str__(self):
        return f'{self.condicao.nome} -> {self.tipo.nome}'

# =============================================================================
# A GUIA DE ENCAMINHAMENTO
# =============================================================================

class Encaminhamento(models.Model):
    """
    A solicitação real de encaminhamento do paciente (A Guia).
    """
    STATUS_CHOICES = [
        ('aguardando', 'Aguardando Vaga'),
        ('regulacao', 'Em Regulação Municipal'),
        ('disponivel', 'Disponível para Entrega'),
        ('entregue', 'Entregue ao Paciente (Concluído)'),
        ('upae', 'Aguardando UPAE'),
        ('unificada', 'Fila Unificada (Concluído)'),
        ('cancelado', 'Cancelado'),
    ]

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='encaminhamentos')
    usf = models.ForeignKey(USF, on_delete=models.PROTECT, related_name='encaminhamentos')
    tipo = models.ForeignKey(TipoEncaminhamento, on_delete=models.PROTECT, related_name='encaminhamentos')
    
    data_solicitacao = models.DateTimeField('Data da Solicitação', auto_now_add=True)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='aguardando')
    
    # 1 = Normal, 2 = Prioridade (Idoso, etc), 3 = Urgente (RegraCondicao)
    prioridade = models.IntegerField('Nível de Prioridade', default=1)
    
    motivo = models.TextField('Motivo Clínico/Justificativa', blank=True)
    
    # Campos que o seu Hub lê para mostrar os gráficos e alertas
    mes_retorno = models.IntegerField('Mês de Retorno (Previsão)', null=True, blank=True)
    ano_retorno = models.IntegerField('Ano de Retorno', null=True, blank=True)

    duplicata_de = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        help_text='Se for um encaminhamento repetido, aponte aqui o original.'
    )

    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        verbose_name='Digitado por'
    )

    class Meta:
        verbose_name = 'Encaminhamento'
        verbose_name_plural = 'Encaminhamentos'
        ordering = ['-prioridade', 'data_solicitacao']

    def __str__(self):
        return f'{self.paciente.nome} - {self.tipo.nome} ({self.get_status_display()})'

# =============================================================================
# HISTÓRICO FAMILIAR (Movido para cá, conforme a sua Views exigia)
# =============================================================================

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
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'Histórico Familiar'
        verbose_name_plural = 'Históricos Familiares'

    def __str__(self):
        return f'{self.paciente.nome} - {self.condicao} ({self.get_grau_parentesco_display()})'