from django.urls import path
from . import views

app_name = 'pacientes'

urlpatterns = [
    # Tela de Busca (Hub do Módulo)
    path('', views.hub_pacientes, name='hub'),
    
    # Prontuário 360º do Paciente (Onde a mágica acontece)
    path('<int:pk>/perfil/', views.perfil_paciente, name='perfil'),
]