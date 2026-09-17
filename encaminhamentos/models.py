from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import Paciente, USF, CondicaoSaude

# =============================================================================
# ARQUITETURA AVANÇADA DE REGULAÇÃO E COTAS
# =============================================================================

class Subcategoria(models.Model):
    """
    Classificação macro do encaminhamento.
    Ex: 'Consulta Especializada', 'Exame de Imagem', 'Ultrassonografia'.
    """
    nome = models.CharField('Subcategoria', max_length=100, unique=True)
    cota_padrao = models.PositiveIntegerField(
        'Cota Mensal Padrão (Compartilhada)', default=0,
        help_text='Créditos que a unidade recebe para gastar livremente com qualquer exame/consulta deste grupo.'
    )
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Subcategoria'
        verbose_name_plural = 'Subcategorias'
        ordering = ['nome']

    def __str__(self):
        return self.nome

class ConfigCotaSubcategoria(models.Model):
    """
    Permite definir um 'Pote de Cotas' específico para uma USF.
    Ex: A USF Centro recebe 10 USGs compartilhadas, enquanto o padrão é 4.
    """
    usf = models.ForeignKey(USF, on_delete=models.CASCADE, related_name='cotas_subcategorias')
    subcategoria = models.ForeignKey(Subcategoria, on_delete=models.CASCADE, related_name='configuracoes_cotas')
    quantidade = models.PositiveIntegerField('Quantidade Específica da USF')

    class Meta:
        verbose_name = 'Configuração de Cota da Subcategoria por USF'
        verbose_name_plural = 'Configurações de Cotas de Subcategoria por USF'
        unique_together = ['usf', 'subcategoria']

    def __str__(self):
        return f'{self.subcategoria.nome} na {self.usf.nome} = {self.quantidade}'

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
    
    # --- NOVAS REGRAS DE IDADE ---
    idade_minima = models.PositiveIntegerField(
        'Idade Mínima (Anos)', null=True, blank=True,
        help_text='Ex: 60 para Geriatria. Deixe em branco se não houver limite.'
    )
    idade_maxima = models.PositiveIntegerField(
        'Idade Máxima (Anos)', null=True, blank=True,
        help_text='Ex: 14 para Pediatria. Deixe em branco se não houver limite.'
    )
    # -----------------------------
    
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
    
    # --- NOVOS CAMPOS PARA CONTROLE DE TEMPO E OBSERVAÇÕES ---
    data_solicitacao = models.DateField('Data da Solicitação Original', default=timezone.now)
    data_status_atual = models.DateField('Data de Entrada no Status Atual', default=timezone.now)
    observacao = models.TextField('Observações da Guia', blank=True)
    # ---------------------------------------------------------

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

    @property
    def dias_no_status(self):
        """Calcula quantos dias a guia está presa no status atual"""
        from datetime import date
        if self.data_status_atual:
            hoje = date.today()
            if isinstance(self.data_status_atual, date):
                return (hoje - self.data_status_atual).days
            else:
                return (hoje - self.data_status_atual.date()).days
        return 0

    @property
    def alerta_idade_incompativel(self):
        """
        MÁGICA DO SISTEMA: Verifica dinamicamente se o paciente fez aniversário 
        e saiu da faixa etária permitida enquanto aguardava na fila.
        """
        if not getattr(self.paciente, 'data_nascimento', None):
            return False # Se não tem data de nascimento, não temos como saber

        idade_atual = self.paciente.idade
        
        if idade_atual is None:
            return False

        # Verifica se ficou mais novo do que o mínimo (raro)
        if self.tipo.idade_minima is not None and idade_atual < self.tipo.idade_minima:
            return True
            
        # Verifica se ficou mais velho do que o máximo permitido (Ex: Fez 13 anos na fila da pediatria)
        if self.tipo.idade_maxima is not None and idade_atual > self.tipo.idade_maxima:
            return True
            
        return False

# =============================================================================
# HISTÓRICO DE TRAMITAÇÃO DA GUIA (NOVO!)
# =============================================================================

class HistoricoEncaminhamento(models.Model):
    """
    Guarda todos os passos da guia. Assim não perdemos nenhuma observação antiga!
    """
    encaminhamento = models.ForeignKey(Encaminhamento, on_delete=models.CASCADE, related_name='historicos')
    status = models.CharField('Status na época', max_length=20, choices=Encaminhamento.STATUS_CHOICES)
    observacao = models.TextField('Observação Registada', blank=True)
    data_registro = models.DateTimeField('Data e Hora da Mudança', auto_now_add=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        verbose_name='Atualizado por'
    )

    class Meta:
        verbose_name = 'Histórico do Encaminhamento'
        verbose_name_plural = 'Históricos dos Encaminhamentos'
        ordering = ['-data_registro'] # O mais recente aparece primeiro

    def __str__(self):
        return f'{self.encaminhamento.paciente.nome} - {self.get_status_display()}'