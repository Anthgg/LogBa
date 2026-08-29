# Procedimientos Operativos de Rollback

## 1. Rollback Inmediato de Backend Cloud Run
Cloud Run preserva de forma inmutable todas las revisiones anteriores desplegadas.
Para revertir el tráfico a una revisión previa conocida:

```bash
# 1. Listar revisiones disponibles
gcloud run revisions list --service=logba-api --region=southamerica-west1

# 2. Redirigir el 100% del tráfico a la revisión anterior
gcloud run services update-traffic logba-api \
  --region=southamerica-west1 \
  --to-revisions=logba-api-PREVIOUS_REVISION=100
```

## 2. Rollback Inmediato de Frontend Cloud Run
```bash
# 1. Listar revisiones de frontend
gcloud run revisions list --service=fronlog-web --region=southamerica-west1

# 2. Redirigir el 100% del tráfico a la revisión previa
gcloud run services update-traffic fronlog-web \
  --region=southamerica-west1 \
  --to-revisions=fronlog-web-PREVIOUS_REVISION=100
```

## 3. Política de Rollback de Base de Datos
- **Regla Fundamental**: NUNCA ejecutar `alembic downgrade` de forma automática ante un fallo de aplicación.
- Primero, realizar el rollback de la versión del contenedor de Backend a la revisión compatible anterior.
- Evaluar si la estructura de datos es compatible o si requiere intervención manual controlada.
- Ejecutar downgrade solo si no existe riesgo de pérdida de datos transaccionales.
