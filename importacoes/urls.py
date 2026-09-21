from django.urls import path
from . import views

app_name = 'importacoes'

urlpatterns = [
    # Dashboard de Importações
    path('', views.hub_importacoes, name='hub'),
    
    # Rotas de Upload (Os 3 motores!)
    path('pacientes/', views.importar_pacientes_csv, name='pacientes_csv'),
    path('condicoes/', views.importar_condicoes_csv, name='condicoes_csv'),
    path('territorio/', views.importar_territorio_csv, name='territorio_csv'),
]