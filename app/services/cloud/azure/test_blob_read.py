# app/services/cloud/azure/run_blob_test.py
from app.services.cloud.azure.azure_blob import AzureBlobService

# Instanciamos el servicio de Blob
blob_service = AzureBlobService()

# Leemos el CSV definido en el .env
df = blob_service.read_csv_from_blob()

# Mostramos las primeras filas
print(df.head())
