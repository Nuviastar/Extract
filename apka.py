import streamlit as st
import fitz  # PyMuPDF
import base64
import json
import pandas as pd
from openai import OpenAI

# --- WYGLĄD STRONY ---
st.set_page_config(page_title="DataExtract AI", page_icon="⚡", layout="centered")

st.title("DataExtract AI - Asystent Dokumentów")

# --- ZABEZPIECZENIE PRAWNE (CHECKBOX) ---
st.markdown("### 🔒 Akceptacja Warunków Testowych")

with st.expander("📄 Przeczytaj Warunki Testowania (Zasada AS-IS) i Wyłączenie Odpowiedzialności"):
    st.markdown("""
    **Wstęp**
    Niniejszy dokument określa zasady korzystania z testowej wersji oprogramowania DataExtract AI („Narzędzie”). Projekt rozwijany jest niezależnie, a jego głównym twórcą i administratorem jest Adam Kotyras („Twórca”). Narzędzie udostępniane jest wyłącznie w celach testowych (wersja Beta B2B).
    
    **1. Charakter testowy („as is”)**
    Narzędzie udostępniane jest w stanie „takim, w jakim jest” („as is”).
    Twórca nie udziela żadnych gwarancji dotyczących:
    * bezbłędności działania
    * ciągłości dostępności
    * przydatności do określonych celów biznesowych
    Narzędzie może zawierać błędy i ulegać zmianom.
    
    **2. Obowiązek weryfikacji danych**
    Narzędzie wykorzystuje sztuczną inteligencję do przetwarzania danych (np. kwot, NIP, dat).
    👉 **Klient zobowiązany jest do samodzielnej i ostatecznej weryfikacji wszystkich wyników** przed ich użyciem w księgowości, rozliczeniach podatkowych czy systemach firmowych. Narzędzie ma charakter wyłącznie pomocniczy.
    
    **3. Ograniczenie odpowiedzialności**
    Korzystanie z Narzędzia odbywa się na własne ryzyko Klienta.
    👉 W maksymalnym zakresie dopuszczalnym przez prawo Twórca nie ponosi odpowiedzialności za błędy w danych wygenerowanych przez Narzędzie, straty finansowe, błędy podatkowe, kary, odsetki ani decyzje podjęte na podstawie wyników.
    👉 Całkowita odpowiedzialność Twórcy (jeśli wystąpi) ograniczona jest do kwoty 0 zł (wersja testowa).
    
    **4. Dane i prywatność**
    * Narzędzie może korzystać z zewnętrznych usług (np. API AI).
    * System projektowany jest w sposób minimalizujący przechowywanie danych.
    * Twórca nie przechowuje danych w sposób celowy i trwały.
    👉 Klient odpowiada za legalność danych, posiadanie zgód (RODO) oraz treść przesyłanych dokumentów.
    
    **5. Charakter testowy i brak opłat**
    Narzędzie udostępniane jest bezpłatnie na okres testowy. Twórca zastrzega możliwość zmiany funkcjonalności lub zakończenia dostępu w dowolnym momencie.
    
    **6. Akceptacja warunków**
    Korzystanie z Narzędzia oznacza akceptację niniejszych warunków.
    """)

zgoda = st.checkbox("Rozumiem, że to wersja testowa AI. Biorę na siebie pełny obowiązek weryfikacji wygenerowanych kwot i danych przed ich użyciem, oraz akceptuję powyższe warunki.")

if not zgoda:
    st.warning("Musisz zaznaczyć powyższą zgodę, aby odblokować system i móc wgrywać dokumenty.")
    st.stop()

st.success("Zgoda zaakceptowana. Możesz rozpocząć pracę.")
st.markdown("---")

# --- WYBÓR BRANŻY I PROMPTY ---
rodzaj_dokumentu = st.selectbox(
    "Wybierz rodzaj dokumentu, który chcesz przetworzyć:",
    ("Wybierz branżę...", "Faktura Kosztowa (Księgowość)", "List Przewozowy CMR (Transport)", "Dokument WZ (Budowlanka)")
)

if rodzaj_dokumentu == "Faktura Kosztowa (Księgowość)":
    aktywny_prompt = """
    Jesteś wybitnym analitykiem finansowym i księgowym. Otrzymałeś skan faktury VAT lub rachunku.
    Znajdź w nim i zwróć WYŁĄCZNIE w formacie JSON następujące dane.
    
    RYGOR FORMATOWANIA:
    - NIP zwracaj jako jednolity ciąg cyfr, bez myślników (np. 1234567890).
    - Kwoty zwracaj jako SAME LICZBY (integer lub float, np. 1500 lub 1500.50). Bez "PLN" czy "zł".
    
    Pola do wyciągnięcia:
    - "Numer faktury": pełny numer dokumentu (jeśli brak, wpisz null)
    - "Data wystawienia": w formacie DD.MM.RRRR (jeśli brak, wpisz null)
    - "NIP Sprzedawcy": numer NIP firmy wystawiającej fakturę bez myślników (jeśli brak, wpisz null)
    - "NIP Nabywcy": numer NIP firmy kupującej bez myślników (jeśli brak, wpisz null)
    - "Kwota Netto [PLN]": wartość netto (jeśli są grosze, ZAMIEŃ KROPKĘ NA PRZECINEK i zwróć jako tekst, np. "2000,50")
    - "Stawka VAT [%]": główna stawka VAT (TYLKO CYFRY, np. 23)
    - "Kwota Brutto [PLN]": wartość brutto (jeśli są grosze, ZAMIEŃ KROPKĘ NA PRZECINEK i zwróć jako tekst, np. "2460,50")
    """
elif rodzaj_dokumentu == "List Przewozowy CMR (Transport)":
    aktywny_prompt = """
    Jesteś głównym spedytorem i analitykiem w firmie transportowej. Otrzymałeś skan listu przewozowego (np. CMR) lub dokumentu dostawy.
    Znajdź w nim i zwróć WYŁĄCZNIE w formacie JSON następujące dane.
    
    RYGOR FORMATOWANIA:
    - Wszelkie wagi i liczby zwracaj jako SAME CYFRY (integer lub float, np. 24000). Usuń słowa takie jak "kg", "tony", "t".
    - Rejestracje pojazdów zwracaj jako ciąg znaków bez spacji (np. PO12345).
    
    Pola do wyciągnięcia:
    - "Numer dokumentu": numer listu przewozowego lub CMR (jeśli brak, wpisz null)
    - "Data załadunku": w formacie DD.MM.RRRR (jeśli brak, wpisz null)
    - "Nadawca towaru": nazwa firmy wydającej towar (jeśli brak, wpisz null)
    - "Miejsce załadunku (Miasto)": tylko nazwa miasta, w którym załadowano towar
    - "Odbiorca towaru": nazwa firmy odbierającej towar (jeśli brak, wpisz null)
    - "Miejsce rozładunku (Miasto)": tylko nazwa miasta, do którego jedzie towar
    - "Waga towaru [kg]": łączna waga ładunku (TYLKO CYFRY, np. 24500)
    - "Numer rejestracyjny pojazdu": rejestracja ciągnika lub naczepy bez spacji (jeśli brak, wpisz null)
    """
elif rodzaj_dokumentu == "Dokument WZ (Budowlanka)":
    aktywny_prompt = """
    Jesteś kierownikiem budowy i analitykiem kosztów. Otrzymałeś skan dokumentu wydania z hurtowni (WZ), faktury za materiały lub kosztorysu.
    Znajdź w nim i zwróć WYŁĄCZNIE w formacie JSON następujące dane.
    
    RYGOR FORMATOWANIA:
    - Kwoty zwracaj jako SAME LICZBY (integer lub float, np. 4500.50). Bez "PLN", "zł", itp.
    
    Pola do wyciągnięcia:
    - "Numer dokumentu": numer WZ, zamówienia lub faktury (jeśli brak, wpisz null)
    - "Data wydania": w formacie DD.MM.RRRR (jeśli brak, wpisz null)
    - "Dostawca (Hurtownia)": nazwa firmy, która sprzedała materiały (jeśli brak, wpisz null)
    - "Miejsce dostawy / Nazwa Inwestycji": gdzie dostarczono towar (np. "Budowa ul. Polna", jeśli brak wpisz null)
    - "Osoba odbierająca": imię i nazwisko pracownika, który odebrał towar (jeśli brak, wpisz null)
    - "Kwota za materiały [PLN]": łączna wartość dokumentu (jeśli są grosze, ZAMIEŃ KROPKĘ NA PRZECINEK i zwróć jako tekst, np. "2460,50")
    """
elif rodzaj_dokumentu == "Wybierz branżę...":
    st.info("Wybierz rodzaj dokumentu z listy powyżej, aby rozpocząć.")
    st.stop()

# --- STYLIZACJA CSS ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stButton>button {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white;
        font-size: 20px !important;
        font-weight: bold;
        border-radius: 8px;
        padding: 15px 30px;
        border: none;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(75, 108, 183, 0.4);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- NAGŁÓWEK ---
st.markdown("<h1 style='text-align: center; color: #182848; font-size: 3rem;'>Automatyzator Umów ⚡</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.2rem; color: #666;'>Wgraj umowy (PDF), a sztuczna inteligencja wyciągnie z nich dane do gotowego pliku Excel.</p>", unsafe_allow_html=True)
st.divider()

# --- UPLOADER PLIKÓW I SILNIK AI ---
uploaded_files = st.file_uploader("Wybierz pliki PDF", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Przetwórz i wygeneruj Excela"):
        with st.spinner("Sztuczna inteligencja czyta dokumenty (to może zająć kilkanaście sekund)..."):
            
            # Pobranie klucza z chmury Streamlit
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            wszystkie_dane = []
            
            try:
                for file in uploaded_files:
                    # Zamiana PDF na obraz
                    doc = fitz.open(stream=file.getvalue(), filetype="pdf")
                    strona = doc.load_page(0)
                    pix = strona.get_pixmap(dpi=150)
                    img_base64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
                    
                    # Wysłanie prosto do OpenAI (z pominięciem lokalnego FastAPI)
                    response = client.chat.completions.create(
                        model="gpt-mini-40",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": aktywny_prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                                ]
                            }
                        ],
                        response_format={"type": "json_object"}
                    )
                    
                    wynik_json = json.loads(response.choices[0].message.content)
                    wszystkie_dane.append(wynik_json)
                
                # Zapis i pobieranie Excela (CSV)
                if wszystkie_dane:
                    df = pd.DataFrame(wszystkie_dane)
                    csv_buffer = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    
                    st.success("✅ Gotowe! Pobierz swój plik poniżej.")
                    st.download_button(
                        label="📥 Pobierz Gotowy Plik Excel (CSV)",
                        data=csv_buffer,
                        file_name="Wyniki_DataExtract.csv",
                        mime="text/csv"
                    )
                    
            except Exception as e:
                st.error(f"❌ Wystąpił błąd podczas analizy: {e}")
