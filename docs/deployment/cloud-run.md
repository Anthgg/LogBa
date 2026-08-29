# Configuración y Despliegue en Cloud Run

## Parámetros Canónicos del Servicio

### Backend (`logba-api`)
- **Región**: `southamerica-west1`
- **CPU**: 1 vCPU
- **Memoria**: 512 MiB
- **Concurrencia**: 80 solicitudes concurrentes por instancia
- **Instancias Mínimas**: 0 (Auto-scaling con scale-to-zero)
- **Instancias Máximas**: 10
- **Ingress**: All (Público autenticado)
- **Liveness Probe**: `GET /live`
- **Readiness Probe**: `GET /ready`

### Frontend (`fronlog-web`)
- **Región**: `southamerica-west1`
- **CPU**: 1 vCPU
- **Memoria**: 256 MiB
- **Concurrencia**: 80
- **Health Check**: `GET /healthz`
