from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import USF, MicroArea, Paciente, CondicaoSaude

# ==============================================================================
# 1. MAPEAMENTO GEOGRÁFICO (RUAS)
# ==============================================================================

class Logradouro(models.Model):
    """Ruas, Avenidas, Travessas que pertencem a uma USF."""
    usf = models.ForeignKey(USF, on_delete=models.PROTECT, related_name='logradouros')
    logradouro = models.CharField('Nome do Logradouro', max_length=200)
    bairro = models.CharField('Bairro', max_length=100)
    cep = models.CharField('CEP', max_length=8, blank=True)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Logradouro'
        verbose_name_plural = 'Logradouros'
        ordering = ['logradouro']
        unique_together = ['usf', 'logradouro', 'bairro']

    def __str__(self):
        return f"{self.logradouro} - {self.bairro}"


class VinculoLogradouro(models.Model):
    """
    Define qual pedaço da rua pertence a qual Micro-área (ACS).
    Ex: A Rua X, do número 1 ao 100, é da Micro-área 01.
    """
    logradouro = models.ForeignKey(Logradouro, on_delete=models.CASCADE, related_name='vinculos')
    micro_area = models.ForeignKey(MicroArea, on_delete=models.CASCADE, related_name='logradouros_vinculados')
    
    data_inicio = models.DateField('Data de Início do Vínculo', default=timezone.now)
    data_fim = models.DateField('Data de Fim do Vínculo', null=True, blank=True)
    
    numero_inicial = models.IntegerField('Número Inicial', null=True, blank=True)
    numero_final = models.IntegerField('Número Final', null=True, blank=True)
    
    motivo = models.CharField('Motivo da alteração', max_length=200, blank=True, help_text='Ex: Redivisão de área')

    class Meta:
        verbose_name = 'Vínculo de Logradouro e Micro-área'
        verbose_name_plural = 'Vínculos de Logradouros'

    def __str__(self):
        return f"{self.logradouro.logradouro} -> {self.micro_area.codigo}"

# ==============================================================================
# 2. MOTOR DE RISCO FAMILIAR (COELHO / SAVASSI)
# ==============================================================================

class SentinelaRisco(models.Model):
    """
    Regras que dão pontos de risco à família.
    Baseado na Escala de Risco Familiar de Coelho e Savassi.
    """
    TIPOS = [
        ('domicilio', 'Condição do Domicílio (Saneamento, Água, etc)'),
        ('individual', 'Condição Individual Marcada à Mão (Ex: Desnutrição)'),
        ('idade', 'Idade Automática (Ex: Menor de 1 ano, Maior de 70)'),
        ('condicao', 'Condição de Saúde Automática (Ex: Gestante, Acamado)'),
    ]

    tipo = models.CharField('Tipo de Sentinela', max_length=20, choices=TIPOS)
    nome = models.CharField('Nome do Fator de Risco', max_length=150)
    codigo = models.SlugField('Código Interno', unique=True)
    peso = models.IntegerField('Pontos de Risco (Peso)', default=1, help_text='Quantos pontos este fator soma na família.')
    
    # Se for tipo "condicao", o sistema lê esta tabela automaticamente
    condicao_saude = models.ForeignKey(CondicaoSaude, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Se for tipo "idade", o sistema calcula pela data de nascimento
    idade_minima = models.IntegerField('Idade Mínima', null=True, blank=True)
    idade_maxima = models.IntegerField('Idade Máxima', null=True, blank=True)
    
    observacao = models.TextField('Observação / Critério Clínico', blank=True)
    ativo = models.BooleanField('Ativo', default=True)

    class Meta:
        verbose_name = 'Sentinela de Risco'
        verbose_name_plural = 'Sentinelas de Risco'
        ordering = ['tipo', '-peso', 'nome']

    def __str__(self):
        return f"[{self.peso} pts] {self.nome}"


class FamiliaScore(models.Model):
    """
    Agrupador familiar. A base é o CPF do Responsável.
    """
    CLASSIFICACOES = [
        ('R0', 'R0 - Sem Risco (0 a 4 pontos)'),
        ('R1', 'R1 - Risco Baixo (5 a 6 pontos)'),
        ('R2', 'R2 - Risco Médio (7 a 8 pontos)'),
        ('R3', 'R3 - Risco Alto (9 ou mais pontos)'),
    ]

    usf = models.ForeignKey(USF, on_delete=models.PROTECT, related_name='familias')
    cpf_responsavel = models.CharField('CPF do Responsável', max_length=11)
    nome_responsavel = models.CharField('Nome do Responsável', max_length=200)
    
    # Endereço unificado da família
    logradouro = models.CharField('Logradouro', max_length=200, blank=True)
    numero = models.CharField('Número', max_length=10, blank=True)
    complemento = models.CharField('Complemento', max_length=100, blank=True)
    bairro = models.CharField('Bairro', max_length=100, blank=True)
    cep = models.CharField('CEP', max_length=8, blank=True)
    ponto_referencia = models.CharField('Ponto de Referência', max_length=200, blank=True)
    numero_comodos = models.IntegerField('Nº de Cômodos', null=True, blank=True)
    
    # Resultados do Cálculo
    score_total = models.IntegerField('Score Total (Pontos)', default=0)
    classificacao = models.CharField('Classificação de Risco', max_length=2, choices=CLASSIFICACOES, default='R0')
    
    ultima_atualizacao = models.DateTimeField('Última Atualização do Score', auto_now=True)

    class Meta:
        verbose_name = 'Score Familiar'
        verbose_name_plural = 'Scores Familiares'
        unique_together = ['usf', 'cpf_responsavel']

    def __str__(self):
        return f"Família {self.nome_responsavel} - Score: {self.score_total} ({self.classificacao})"

    def calcular_score(self):
        """
        O GRANDE MOTOR: Calcula os pontos da família juntando os problemas 
        da casa (domicílio) com as doenças de cada membro!
        """
        pontos = 0
        
        # 1. Pontos do Domicílio (Saneamento, lixo, etc)
        sentinelas_domicilio = FamiliaSentinela.objects.filter(familia=self).select_related('sentinela')
        for sd in sentinelas_domicilio:
            pontos += sd.sentinela.peso
            
        # Busca todos os membros vivos e ativos desta família
        membros = Paciente.objects.filter(usf=self.usf, cpf_responsavel=self.cpf_responsavel, ativo=True, obito=False)
        
        # Busca as sentinelas automáticas para não consultar a base várias vezes
        sentinelas_auto_idade = SentinelaRisco.objects.filter(tipo='idade', ativo=True)
        sentinelas_auto_condicao = SentinelaRisco.objects.filter(tipo='condicao', ativo=True)

        for membro in membros:
            # 2. Pontos Individuais Marcados à mão (Ex: Acamado temporário, Drogadição)
            sentinelas_ind = MembroSentinela.objects.filter(paciente=membro, familia=self).select_related('sentinela')
            for si in sentinelas_ind:
                pontos += si.sentinela.peso
                
            # 3. Pontos Automáticos por Idade
            idade_membro = membro.idade
            if idade_membro is not None:
                for sa in sentinelas_auto_idade:
                    minimo = sa.idade_minima if sa.idade_minima is not None else -1
                    maximo = sa.idade_maxima if sa.idade_maxima is not None else 999
                    if minimo <= idade_membro <= maximo:
                        pontos += sa.peso
            
            # 4. Pontos Automáticos por Condição (Diabetes, Hipertensão, Gestante)
            # Se o membro tiver a doença ATIVA, soma os pontos!
            condicoes_ativas = membro.condicoes.filter(data_fim__isnull=True).values_list('condicao_id', flat=True)
            for sc in sentinelas_auto_condicao:
                if sc.condicao_saude_id in condicoes_ativas:
                    pontos += sc.peso
                    
        # 5. Relação Morador / Cômodo
        if self.numero_comodos and self.numero_comodos > 0:
            razao = membros.count() / self.numero_comodos
            if razao > 1:
                pontos += 3 # Ganha 3 pontos de risco por aglomeração!
                
        # Atualiza os valores finais
        self.score_total = pontos
        
        if pontos <= 4: self.classificacao = 'R0'
        elif pontos <= 6: self.classificacao = 'R1'
        elif pontos <= 8: self.classificacao = 'R2'
        else: self.classificacao = 'R3'
        
        return pontos

    def salvar_com_score(self):
        """Calcula e guarda na base de dados num só passo."""
        self.calcular_score()
        self.save()

class FamiliaSentinela(models.Model):
    """Riscos marcados para a Casa inteira (Ex: Falta de água tratada)."""
    familia = models.ForeignKey(FamiliaScore, on_delete=models.CASCADE, related_name='sentinelas_domicilio')
    sentinela = models.ForeignKey(SentinelaRisco, on_delete=models.CASCADE)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['familia', 'sentinela']

class MembroSentinela(models.Model):
    """Riscos marcados manualmente para uma pessoa (Ex: Analfabetismo, Desemprego)."""
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='sentinelas')
    familia = models.ForeignKey(FamiliaScore, on_delete=models.CASCADE)
    sentinela = models.ForeignKey(SentinelaRisco, on_delete=models.CASCADE)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    data_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['paciente', 'sentinela']

# ==============================================================================
# FICHA SSA2 (SITUAÇÃO DE SAÚDE - PRODUÇÃO ACS E ENFERMAGEM)
# ==============================================================================
class FichaSSA2(models.Model):
    """Guarda a produção mensal da micro-área."""
    microarea = models.ForeignKey(MicroArea, on_delete=models.CASCADE, related_name='fichas_ssa2')
    mes = models.IntegerField('Mês')
    ano = models.IntegerField('Ano')
    data_preenchimento = models.DateTimeField(auto_now=True)

    # --- Gestantes / Famílias ---
    gest_cadastradas = models.IntegerField(null=True, blank=True)
    gest_acompanhadas = models.IntegerField(null=True, blank=True)
    gest_vacina_em_dia = models.IntegerField(null=True, blank=True)
    gest_consulta_mes = models.IntegerField(null=True, blank=True)
    gest_inicio_1_trimestre = models.IntegerField(null=True, blank=True)
    gest_menor_20_anos = models.IntegerField(null=True, blank=True)
    total_familias_cadastradas = models.IntegerField(null=True, blank=True)
    visita_domiciliar_acs = models.IntegerField(null=True, blank=True)

    # --- Doenças ---
    diab_cadastrados = models.IntegerField(null=True, blank=True)
    diab_acompanhados = models.IntegerField(null=True, blank=True)
    hiper_cadastrados = models.IntegerField(null=True, blank=True)
    hiper_acompanhados = models.IntegerField(null=True, blank=True)
    tb_cadastrados = models.IntegerField(null=True, blank=True)
    tb_acompanhados = models.IntegerField(null=True, blank=True)
    han_cadastrados = models.IntegerField(null=True, blank=True)
    han_acompanhados = models.IntegerField(null=True, blank=True)

    # --- Hosp ---
    hosp_menor_5a_pneumonia = models.IntegerField(null=True, blank=True)
    hosp_menor_5a_desidratacao = models.IntegerField(null=True, blank=True)
    hosp_abuso_alcool = models.IntegerField(null=True, blank=True)
    hosp_complicacao_diabetes = models.IntegerField(null=True, blank=True)
    hosp_outras_causas = models.IntegerField(null=True, blank=True)
    hosp_total = models.IntegerField(null=True, blank=True)
    hosp_psiquiatrico = models.IntegerField(null=True, blank=True)

# --- Crianças ---
    nascidos_vivos_mes = models.IntegerField(null=True, blank=True)
    rn_pesados_ao_nascer = models.IntegerField(null=True, blank=True)
    rn_baixo_peso = models.IntegerField(null=True, blank=True)
    
    # 🚀 O CAMPO QUE FALTAVA!
    cria_0_3m_total = models.IntegerField(null=True, blank=True) 
    
    cria_0_3m_aleitamento_exclusivo = models.IntegerField(null=True, blank=True)
    cria_0_3m_aleitamento_misto = models.IntegerField(null=True, blank=True)
    cria_0_11m_total = models.IntegerField(null=True, blank=True)
    cria_0_11m_vacina_em_dia = models.IntegerField(null=True, blank=True)
    cria_0_11m_pesadas = models.IntegerField(null=True, blank=True)
    cria_0_11m_desnutridas = models.IntegerField(null=True, blank=True)
    cria_12_23m_total = models.IntegerField(null=True, blank=True)
    cria_12_23m_vacina_em_dia = models.IntegerField(null=True, blank=True)
    cria_12_23m_pesadas = models.IntegerField(null=True, blank=True)
    cria_12_23m_desnutridas = models.IntegerField(null=True, blank=True)
    cria_menor_2a_total = models.IntegerField(null=True, blank=True)
    cria_menor_2a_diarreia = models.IntegerField(null=True, blank=True)
    cria_menor_2a_diarreia_tro = models.IntegerField(null=True, blank=True)
    cria_menor_2a_ira = models.IntegerField(null=True, blank=True)

    # --- Obitos ---
    obito_menor_28d_diarreia = models.IntegerField(null=True, blank=True)
    obito_menor_28d_ira = models.IntegerField(null=True, blank=True)
    obito_menor_28d_outras = models.IntegerField(null=True, blank=True)
    obito_28d_11m_diarreia = models.IntegerField(null=True, blank=True)
    obito_28d_11m_ira = models.IntegerField(null=True, blank=True)
    obito_28d_11m_outras = models.IntegerField(null=True, blank=True)
    obito_menor_1a_diarreia = models.IntegerField(null=True, blank=True)
    obito_menor_1a_ira = models.IntegerField(null=True, blank=True)
    obito_menor_1a_outras = models.IntegerField(null=True, blank=True)
    obito_mulher_10_14a = models.IntegerField(null=True, blank=True)
    obito_mulher_15_49a = models.IntegerField(null=True, blank=True)
    obito_outras_causas = models.IntegerField(null=True, blank=True)
    obito_total = models.IntegerField(null=True, blank=True)
    obito_adolescente_violencia = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Ficha SSA2'
        verbose_name_plural = 'Fichas SSA2'
        unique_together = ['microarea', 'mes', 'ano'] # Impede criar duas fichas para o mesmo mês/MA

    def __str__(self):
        return f"SSA2 - MA {self.microarea.codigo} ({self.mes}/{self.ano})"