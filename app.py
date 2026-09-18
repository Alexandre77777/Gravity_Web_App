import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

DEMO_FILE = Path(__file__).parent / "data" / "terrain_demo.csv"
DEFAULT_SERVER = "https://gravity-api-server.fastapicloud.dev"
REQUIRED_COLUMNS = [
    'latitude', 'longitude', 'elevation_m', 'slope', 'curvature', 
    'tpi_7', 'tpi_31', 'tpi_121', 'roughness_7', 'roughness_31', 'relief_31'
]

def clear_result():
    st.session_state.pop('result', None)

def request_result(url, rows, output):
    response = requests.post(url, params={"output":output}, json=rows, timeout=120)
    if not response.ok:
        try:
            message = response.json().get("detail", response.text)
        except ValueError:
            message = response.text
        raise ValueError(f"Ошибка сервера ({response.status_code}): {message}")
    return response.text if output == 'html' else response.json()

def result_to_geojson(data):
    features = []
    for row in data.to_dict(orient='records'):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row['longitude'], row['latitude']]},
            "properties": {key: value for key, value in row.items() if key not in ('latitude', 'longitude')}
        })
    return json.dumps({"type": "FeatureCollection", "features": features})

st.set_page_config(page_title="Гравитационное влияние рельефа", layout='wide', page_icon="🏔️")
st.title('🏔️ Гравитационное влияние рельефа')
st.write(
    "Загрузите CSV с координатами и подготовленными признаками рельефа."
    "Веб-интерфейс передаст их в API: модель и расчёт выполняются на сервере."
)

st.sidebar.header('⚙️ Параметры')
server = st.sidebar.text_input('Адрес сервера API', DEFAULT_SERVER, on_change=clear_result).strip().rstrip('/')
uploaded = st.sidebar.file_uploader('📂 CSV с признаками рельефа', type='csv', on_change=clear_result)

if uploaded is None:
    st.sidebar.caption('Используется демонстрационный файл terrain_demo.csv')

try:
    data = pd.read_csv(uploaded if uploaded is not None else DEMO_FILE)
except Exception as error:
    st.error(f'Не удалось прочитать CSV: {error}')
    st.stop()

missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]

if data.empty or missing:
    st.error(f'Нужна непустая таблица. Отсутствующие столбцы: {missing}')
    st.stop()

st.sidebar.caption(f'Точек: {len(data)}, столбцов: {len(data.columns)}')
with st.expander('📋Исходные данные - первые 10 строк'):
    st.dataframe(data.head(10), hide_index=True, width='stretch')

if st.sidebar.button('🚀 Рассчитать', type='primary', width='stretch', disabled=not server):
    clear_result()
    try:
        rows = data[REQUIRED_COLUMNS].to_dict(orient='records')
        url = f"{server}/predict"
        with st.spinner('Сервер выполняет расчёт и строит карту...'):
            result = pd.DataFrame(request_result(url, rows, "json"))
            map_html = request_result(url, rows, "html")
        st.session_state['result'] = (result, map_html)
    except Exception as error:
        st.error(f'Не удалось получить результат: {error}')

if 'result' in st.session_state:
    result, map_html = st.session_state['result']
    st.subheader('🗺️ Карта расчётного поля')
    st.caption(f'Обработано точек: {len(result)}. Значение гравитационного влияния рельефа - в мГал.')
    components.html(map_html, height=740)

    csv_column, geojson_column, map_column = st.columns(3)

    csv_column.download_button(
        '📄 Скачать CSV', result.to_csv(index=False).encode('utf-8-sig'),
        file_name='terrain_prediction.csv', mime='text/csv', type='primary', width='stretch'
    )

    geojson_column.download_button(
        '📍 Скачать GeoJSON', result_to_geojson(result),
        file_name='terrain_prediction.geojson', mime='application/geo+json', type='primary', width='stretch'
    )

    map_column.download_button(
        '🗺️ Скачать HTML', map_html,
        file_name='terrain_map.html', mime='text/html', type='primary', width='stretch'
    )

    st.subheader('📊 Таблица результатов')
    st.dataframe(result, hide_index=True, width='stretch', height=300)

