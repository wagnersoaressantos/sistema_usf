from django.urls import path
from . import views

app_name = 'farmacia'

urlpatterns = [
    # Dashboard / Hub Central da Farmácia
    path('', views.hub_farmacia, name='hub'),
    
    # Tela inicial do balcão (busca de pacientes para dispensação)
    path('balcao/', views.balcao_busca, name='balcao_busca'),
    
    # Rota de entregar os remédios
    path('atender/<int:paciente_id>/', views.atender_receita, name='atender_receita'),
    
    # ROTAS: Gestão de Estoque
    path('estoque/', views.estoque_lista, name='estoque_lista'),
    path('estoque/entrada/', views.entrada_lote, name='entrada_lote'),
    
    # ROTAS: Catálogo REMUME Restrito
    path('catalogo/', views.catalogo_lista, name='catalogo_lista'),
    path('catalogo/novo/', views.catalogo_salvar, name='catalogo_criar'),
    path('catalogo/<int:pk>/editar/', views.catalogo_salvar, name='catalogo_editar'),
    
    # ROTAS: Relatórios de Faltas
    path('relatorios/faltas/', views.relatorio_faltas, name='relatorio_faltas'),
]