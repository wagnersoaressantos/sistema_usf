from django.db import models
from django.contrib.auth.models import User
from core.models import USF, Paciente
from django.core.exceptions import ValidationError # 🚀 CORREÇÃO 1: Faltava o import da trava!

class Medicamento(models.Model):
    """Catálogo Municipal de Medicamentos (REMUME) e Insumos"""
    
    TIPO_CHOICES = [
        ('MED', 'Medicamento'),
        ('INS', 'Insumo / Material Técnico'),
    ]

    FORMA_CHOICES = [
        ('COMP', 'Comprimido / Drágea'),
        ('CAPS', 'Cápsula'),
        ('GOTA', 'Gotas / Solução Oral'),
        ('XARO', 'Xarope'),
        ('INJE', 'Injetável (Ampola)'),
        ('POMA', 'Pomada / Creme'),
        ('PACO', 'Pacote'),
        ('ROLO', 'Rolo / Bobina'),
        ('UNID', 'Unidade Avulsa'),
        ('CX', 'Caixa'),
        ('OUTR', 'Outros'),
    ]

    # 🚀 CORREÇÃO: Tiramos o 'default' e permitimos null/blank
    tipo = models.CharField(max_length=3, choices=TIPO_CHOICES, blank=True, null=True)
    codigo_br = models.CharField("Código BR / CATMAT", max_length=50, blank=True, null=True, help_text="Código oficial do produto (Ex: BR0272906)")
    nome = models.CharField(max_length=255)
    concentracao = models.CharField(max_length=100, blank=True, null=True, help_text="Ex: 500mg, 50mg/ml (Deixe em branco para Insumos)")
    
    # 🚀 CORREÇÃO: Tiramos o 'default' e permitimos null/blank
    forma_farmaceutica = models.CharField(max_length=4, choices=FORMA_CHOICES, blank=True, null=True)
    
    exige_receita_branca = models.BooleanField(default=False, verbose_name="Exige Receita Branca (Controle Simples)")
    exige_receita_controlada = models.BooleanField(default=False, verbose_name="Exige Receita Azul/Amarela (Psicotrópicos)")
    antibiotico = models.BooleanField(default=False, verbose_name="Antibiótico (Retenção de Receita)")
    
    # 🚀 CORREÇÃO: Por padrão, o item entra Inativo (A aguardar curadoria)
    ativo = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Item do Catálogo (REMUME)"
        verbose_name_plural = "Catálogo de Medicamentos e Insumos"
        ordering = ['nome']

    def clean(self):
        # 1. Trava de Estoque ao Desativar
        if not self.ativo and self.pk:
            tem_estoque = self.lotes.filter(quantidade_atual__gt=0).exists()
            if tem_estoque:
                raise ValidationError({'ativo': '🚨 Bloqueado: Não é possível desativar este item, pois ainda existe saldo nas prateleiras!'})
        
        # 2. 🚀 NOVA TRAVA DE CURADORIA: Exigir campos preenchidos para Ativar
        if self.ativo:
            erros = {}
            if not self.tipo:
                erros['tipo'] = 'Para ativar o item no sistema, defina se é Medicamento ou Insumo.'
            if not self.forma_farmaceutica:
                erros['forma_farmaceutica'] = 'Para ativar o item, defina a forma (Caixa, Unidade, Comprimido, etc).'
            
            if erros:
                raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.full_clean() # Força a execução da trava antes de gravar no banco
        super().save(*args, **kwargs)

    @property
    def unidade_medida(self):
        """Traduz a forma farmacêutica para a unidade de contagem no ecrã"""
        if self.forma_farmaceutica in ['COMP', 'CAPS']:
            return 'comprimido(s)/cápsula(s)'
        elif self.forma_farmaceutica in ['GOTA', 'XARO']:
            return 'frasco(s)'
        elif self.forma_farmaceutica == 'INJE':
            return 'ampola(s)'
        elif self.forma_farmaceutica == 'POMA':
            return 'bisnaga(s)'
        elif self.forma_farmaceutica == 'PACO':
            return 'pacote(s)'
        elif self.forma_farmaceutica == 'ROLO':
            return 'rolo(s)'
        elif self.forma_farmaceutica == 'CX':
            return 'caixa(s)'
        return 'unidade(s)'


class LoteEstoque(models.Model):
    """O estoque físico do medicamento na Unidade de Saúde"""
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE, related_name='lotes')
    usf = models.ForeignKey(USF, on_delete=models.CASCADE, related_name='estoque_farmacia')
    
    numero_lote = models.CharField(max_length=50, blank=True, null=True, help_text="Deixe em branco se a USF não controlar o lote exato.")
    quantidade_atual = models.PositiveIntegerField(default=0)
    data_validade = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "Lote de Estoque"
        verbose_name_plural = "Lotes de Estoque"
        ordering = ['data_validade']

    def __str__(self):
        return f"{self.medicamento.nome} - Lote: {self.numero_lote or 'S/L'} (Qtd: {self.quantidade_atual})"


class Dispensacao(models.Model):
    """Registo de entrega do medicamento ao Paciente"""
    usf = models.ForeignKey(USF, on_delete=models.CASCADE, related_name='dispensacoes')
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='medicamentos_recebidos')
    profissional = models.ForeignKey(User, on_delete=models.PROTECT, related_name='dispensacoes_realizadas')
    
    data_dispensacao = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Dispensação"
        verbose_name_plural = "Dispensações"
        ordering = ['-data_dispensacao']

    def __str__(self):
        return f"Entrega a {self.paciente.nome} em {self.data_dispensacao.strftime('%d/%m/%Y')}"


class ItemDispensacao(models.Model):
    """Os remédios específicos dentro de uma entrega (Para permitir levar vários remédios de uma vez)"""
    dispensacao = models.ForeignKey(Dispensacao, on_delete=models.CASCADE, related_name='itens')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.PROTECT)
    lote_utilizado = models.ForeignKey(LoteEstoque, on_delete=models.SET_NULL, null=True, blank=True)
    
    quantidade_entregue = models.PositiveIntegerField()
    
    # 🚀 A MÁGICA DA PREVISÃO DE DEMANDA PROGRAMADA NASCE AQUI (O que você sugeriu!)
    uso_continuo = models.BooleanField(default=False, verbose_name="Uso Contínuo / Repetição", help_text="Marque se o paciente vai precisar retirar este item todos os meses.")
    
    # 🚀 A MÁGICA DA TRAVA ANTISSUPERPOSIÇÃO NASCE AQUI
    posologia_diaria = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, help_text="Quantos toma por dia? (Deixe em branco para insumos)")
    dias_tratamento = models.PositiveIntegerField(blank=True, null=True, help_text="Para quantos dias dá? (Deixe em branco para insumos)")
    data_proxima_retirada = models.DateField(blank=True, null=True, help_text="Quando o paciente pode voltar para pegar mais?")

    # 🚀 O NOVO CAMPO DE AUDITORIA
    justificativa_antecipacao = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Ex: Alteração de posologia médica, Perda/Roubo, etc."
    )

    def __str__(self):
        return f"{self.quantidade_entregue}x {self.medicamento.nome}"

class DemandaReprimida(models.Model):
    """Registo de pacientes que procuraram o remédio e não havia (Falta na Prateleira)"""
    usf = models.ForeignKey(USF, on_delete=models.CASCADE, related_name='demandas_reprimidas')
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='medicamentos_em_falta')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE)
    profissional = models.ForeignKey(User, on_delete=models.PROTECT)
    
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Demanda Reprimida (Falta)"
        verbose_name_plural = "Demandas Reprimidas (Faltas)"
        ordering = ['-data_registro']

    def __str__(self):
        return f"Falta: {self.medicamento.nome} - {self.usf.nome}"

class MovimentacaoEstoque(models.Model):
    """Livro de Registo (Audit Trail) para rastrear tudo o que não for entrega a paciente"""
    
    TIPO_CHOICES = [
        ('ENTRADA_CAF', '📥 Entrada (Recebimento da CAF Central)'),
        ('ENTRADA_TRANSFERENCIA', '📥 Entrada por Transferência (De outra USF)'),
        ('ENTRADA_AJUSTE', '📥 Entrada (Ajuste de inventário)'),
        ('SAIDA_TRANSFERENCIA', '📤 Saída por Transferência (Para outra USF)'),
        ('SAIDA_PERDA', '📤 Saída por Perda / Vencimento / Avaria'),
        ('SAIDA_AJUSTE', '📤 Saída (Ajuste de inventário)'),
    ]

    lote = models.ForeignKey(LoteEstoque, on_delete=models.CASCADE, related_name='movimentacoes')
    tipo_movimento = models.CharField(max_length=25, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField(help_text="Sempre positivo. O sistema soma ou subtrai automaticamente.")
    
    data_movimento = models.DateTimeField(auto_now_add=True)
    justificativa = models.CharField(max_length=255, blank=True, null=True, help_text="Ex: Transferido para USF Centro. Venceu na prateleira.")
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Movimentação de Estoque"
        verbose_name_plural = "Movimentações de Estoque"
        ordering = ['-data_movimento']

    def save(self, *args, **kwargs):
        # 🚀 A MÁGICA LOGÍSTICA: Atualiza a quantidade do Lote automaticamente na hora de salvar!
        if not self.pk: # Só faz a conta se for um registo novo
            if self.tipo_movimento.startswith('ENTRADA'):
                self.lote.quantidade_atual += self.quantidade
            elif self.tipo_movimento.startswith('SAIDA'):
                self.lote.quantidade_atual -= self.quantidade
            self.lote.save()
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_movimento_display()} - {self.quantidade} un. ({self.lote.medicamento.nome})"
