# import pandas as pd
from app.services.cloud.azure.azure_blob import AzureBlobService

# Crear instancia apuntando al contenedor correcto
blob_service = AzureBlobService(container_name="structured-data")

# Nombre exacto del blob (ruta dentro del contenedor)
blob_name = "price_list/precios_clinica_normalizado_v3.csv"

# Leer CSV directamente desde Azure Blob como DataFrame
df = blob_service.load_csv_as_dataframe(blob_name)

# Mostrar algunas filas
print("✅ Primeras filas del CSV leído desde Azure Blob:")
print(df.head())

# Mostrar info general del dataframe
print("\n📊 Info del DataFrame:")
print(df.info())
