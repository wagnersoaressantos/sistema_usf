from django.urls import path
from . import views

app_name = 'pacientes'

urlpatterns = [
    # Hub Clínico e Busca de Pacientes
    path('', views.hub_pacientes, name='hub'),
    
    # 🚀 A Rota do Prontuário 360º
    path('<int:pk>/', views.perfil_paciente, name='perfil'),
]