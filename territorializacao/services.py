import calendar
from datetime import date
from django.db.models import Count, Q
from core.models import Paciente, PacienteCondicao
from .models import MicroArea, FamiliaScore

def preencher_automatico_ssa2(micro_area_id, mes, ano):
    """
    Motor de Inteligência Sanitária Completo.
    Faz a contagem rigorosa de idades, doenças e óbitos cruzando dados do e-SUS.
    """
    try:
        micro_area = MicroArea.objects.get(pk=micro_area_id)
    except MicroArea.DoesNotExist:
        return None

    hoje = date.today()

    # 1. Filtro Base de Pacientes Vivos
    pacientes_vivos = Paciente.objects.filter(
        micro_area=micro_area,
        ativo=True,
        obito=False
    )

    # 2. Contagem de Famílias
    cpfs_responsaveis = pacientes_vivos.exclude(cpf_responsavel='').values_list('cpf_responsavel', flat=True).distinct()
    total_familias = FamiliaScore.objects.filter(
        usf=micro_area.usf, 
        cpf_responsavel__in=cpfs_responsaveis
    ).count()

    # 3. Matemática Temporal Exata (O segredo do e-SUS)
    ultimo_dia_do_mes = calendar.monthrange(ano, mes)[1]
    data_corte = date(ano, mes, ultimo_dia_do_mes)
    
    if ano == hoje.year and mes == hoje.month:
        data_corte = hoje
    
    try:
        data_menos_1_ano = data_corte.replace(year=data_corte.year - 1)
        data_menos_2_anos = data_corte.replace(year=data_corte.year - 2)
        data_corte_20_anos = data_corte.replace(year=data_corte.year - 20)
    except ValueError:
        data_menos_1_ano = data_corte.replace(year=data_corte.year - 1, day=28)
        data_menos_2_anos = data_corte.replace(year=data_corte.year - 2, day=28)
        data_corte_20_anos = data_corte.replace(year=data_corte.year - 20, day=28)

    # 🚀 CÁLCULO EXATO DE 4 MESES ATRÁS (Para a faixa 0 a 3m e 29d)
    mes_4m = data_corte.month - 4
    ano_4m = data_corte.year
    if mes_4m <= 0:
        mes_4m += 12
        ano_4m -= 1
    dia_4m = min(data_corte.day, calendar.monthrange(ano_4m, mes_4m)[1])
    data_menos_4_meses = date(ano_4m, mes_4m, dia_4m)

    # 4. Cruzamento de Doenças Ativas
    condicoes_ativas = PacienteCondicao.objects.filter(
        paciente__micro_area=micro_area,
        paciente__ativo=True,
        paciente__obito=False,
        data_fim__isnull=True
    )

    # 5. Inteligência de Óbitos
    pacientes_mortos = Paciente.objects.filter(
        micro_area=micro_area,
        obito=True,
        data_obito__year=ano,
        data_obito__month=mes
    )
    
    # Lógica de mortalidade materna
    obito_mulher_10_14a = 0
    obito_mulher_15_49a = 0
    for mulher in pacientes_mortos.filter(sexo='F'):
        if mulher.data_nascimento and mulher.data_obito:
            idade_obito = mulher.data_obito.year - mulher.data_nascimento.year - ((mulher.data_obito.month, mulher.data_obito.day) < (mulher.data_nascimento.month, mulher.data_nascimento.day))
            if 10 <= idade_obito <= 14:
                obito_mulher_10_14a += 1
            elif 15 <= idade_obito <= 49:
                obito_mulher_15_49a += 1

    # 6. Devolução do Dicionário Completo
    return {
        'total_familias_cadastradas': total_familias,
        
        # Crianças (Rigorosamente iguais à Ficha Física)
        'nascidos_vivos_mes': pacientes_vivos.filter(data_nascimento__year=ano, data_nascimento__month=mes).count(),
        'cria_0_3m_total': pacientes_vivos.filter(data_nascimento__gt=data_menos_4_meses, data_nascimento__lte=data_corte).count(),
        'cria_0_11m_total': pacientes_vivos.filter(data_nascimento__gt=data_menos_1_ano, data_nascimento__lte=data_corte).count(),
        'cria_12_23m_total': pacientes_vivos.filter(data_nascimento__lte=data_menos_1_ano, data_nascimento__gt=data_menos_2_anos).count(),
        'cria_menor_2a_total': pacientes_vivos.filter(data_nascimento__gt=data_menos_2_anos, data_nascimento__lte=data_corte).count(),
        
        # Gestantes
        'gest_cadastradas': condicoes_ativas.filter(condicao__codigo__icontains='gestante').count(),
        'gest_menor_20_anos': condicoes_ativas.filter(condicao__codigo__icontains='gestante', paciente__data_nascimento__gt=data_corte_20_anos).count(),
        
        # Doenças Crônicas
        'diab_cadastrados': condicoes_ativas.filter(condicao__codigo__icontains='diabet').count(),
        'hiper_cadastrados': condicoes_ativas.filter(condicao__codigo__icontains='hipertens').count(),
        'tb_cadastrados': condicoes_ativas.filter(condicao__codigo__icontains='tuberculose').count(),
        'han_cadastrados': condicoes_ativas.filter(condicao__codigo__icontains='hanseniase').count(),
        
        # Óbitos
        'obito_total': pacientes_mortos.count(),
        'obito_mulher_10_14a': obito_mulher_10_14a,
        'obito_mulher_15_49a': obito_mulher_15_49a,
    }