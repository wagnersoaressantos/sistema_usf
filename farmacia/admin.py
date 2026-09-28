from django.contrib import admin
from .models import Medicamento, LoteEstoque, Dispensacao, ItemDispensacao, MovimentacaoEstoque, DemandaReprimida

@admin.register(Medicamento)
class MedicamentoAdmin(admin.ModelAdmin):
    # 🚀 Atualizamos a lista para mostrar o Código BR e o Tipo!
    list_display = ('codigo_br', 'nome', 'tipo', 'concentracao', 'forma_farmaceutica', 'ativo')
    list_filter = ('tipo', 'forma_farmaceutica', 'antibiotico', 'exige_receita_controlada', 'ativo')
    search_fields = ('nome', 'codigo_br', 'concentracao')
    list_editable = ('ativo',)

# Para vermos o histórico de movimentações dentro da página do Lote
class MovimentacaoEstoqueInline(admin.TabularInline):
    model = MovimentacaoEstoque
    extra = 1
    readonly_fields = ('data_movimento',)

@admin.register(LoteEstoque)
class LoteEstoqueAdmin(admin.ModelAdmin):
    list_display = ('medicamento', 'usf', 'numero_lote', 'quantidade_atual', 'data_validade')
    list_filter = ('usf', 'data_validade')
    search_fields = ('medicamento__nome', 'numero_lote')
    inlines = [MovimentacaoEstoqueInline]

@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ('lote', 'tipo_movimento', 'quantidade', 'data_movimento', 'registrado_por')
    list_filter = ('tipo_movimento', 'data_movimento')
    search_fields = ('lote__medicamento__nome', 'justificativa')

class LoteEstoqueAdmin(admin.ModelAdmin):
    list_display = ('medicamento', 'usf', 'numero_lote', 'quantidade_atual', 'data_validade')
    list_filter = ('usf', 'data_validade')
    search_fields = ('medicamento__nome', 'numero_lote')

# Como a dispensação tem vários itens (remédios), usamos um "Inline" para mostrar tudo junto
class ItemDispensacaoInline(admin.TabularInline):
    model = ItemDispensacao
    extra = 1

@admin.register(Dispensacao)
class DispensacaoAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'usf', 'profissional', 'data_dispensacao')
    list_filter = ('usf', 'data_dispensacao')
    search_fields = ('paciente__nome', 'paciente__cpf')
    inlines = [ItemDispensacaoInline]