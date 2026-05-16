import streamlit as st
import pandas as pd

# Título
st.title("App TCU Nirien 🚀")

# Mensaje simple
st.write("✅ La app está funcionando correctamente")

# Ejemplo de tabla
data = {
    "CANTON": ["San José", "Heredia", "Cartago"],
    "BENEFICIARIOS": [120, 80, 95]
}

df = pd.DataFrame(data)

st.subheader("Ejemplo de datos")
st.dataframe(df)

# Mensaje de prueba del workflow
st.success("🚨 TEST WORKFLOW ACTIVO")
