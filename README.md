<p align="center">
  <h1 align="center"> S E N K A <sub>(selektivno nadgledanje kretanja)</sub></h1>
  <p align="center"><strong>Globalno nadgledanje kretnji  Platforma za geoprostornu inteligenciju u realnom vremenu</strong></p>
  <p align="center">
    <code> // // // </code>
  </p>
</p>

---

**Senka** je kontrolni panel za geoprostornu inteligenciju u realnom vremenu koji agregira podatke sa desetina OSINT (obaveštavanje iz otvorenih izvora) izvora i prikazuje ih na objedinjenom interfejsu mape u noćnom operativnom stilu. Prati avione, brodove, satelite, zemljotrese, zone sukoba, CCTV mreže, GPS ometanje i aktuelne geopolitičke događaje i sve se ažurira u realnom vremenu.

Napravljena sa **Next.js**, **MapLibre GL**, **FastAPI** i **Python**-om, namenjena je analitičarima, istraživačima i entuzijastima koji žele objedinjeni prikaz globalne aktivnosti.

---

##  Mogućnosti

###  Praćenje vazduhoplova

- **Komercijalni letovi** — Pozicije u realnom vremenu preko OpenSky Network mreže (~5.000+ letelica)
- **Privatne letelice** — Laki GA, turboprop i poslovni džetovi se prate posebno
- **Privatni džetovi** — Letelice pojedinaca visoke neto vrednosti sa identifikacijom vlasnika
- **Vojni letovi** — Tankeri, ISR, lovci i transporteri preko adsb.lol vojnog endpointa
- **Akumulacija tragova leta** — Trajni tragovi za sve praćene letelice
- **Detekcija obrasca čekanja** — Automatski označava letelice u kruženju (>300° ukupnog zaokreta)
- **Klasifikacija letelica** — Oblikom tačne SVG ikone: avioni, turboprop, poslovni džetovi, helikopteri
- **Detekcija na zemlji** — Letelice ispod 100ft AGL prikazuju se sivim ikonama

###  Pomorsko praćenje

- **AIS tok plovila** — 25.000+ plovila preko aisstream.io WebSocket-a (realno vreme)
- **Klasifikacija brodova** — Teretni, tankeri, putnički, jahte i vojni tipovi plovila sa ikonama u boji
- **Praćenje udarne grupe nosača** — Svih 11 aktivnih nosača aviona američke mornarice sa OSINT-procenjenim pozicijama
  - Automatsko prikupljanje GDELT vesti za obaveštajne podatke o kretanju nosača
  - 50+ mapiranja geografskih regija u koordinate
  - Pozicije keširane na disku, automatsko ažuriranje u 00:00 i 12:00 UTC
- **Kruzeri i putnički brodovi** — Posvećen sloj za kruzere i trajekte
- **Grupisani prikaz** — Brodovi se grupišu pri niskom zumu sa oznakama broja, razgrupišu se pri povećanju zuma

###  Svemir i sateliti

- **Orbitalno praćenje** — Pozicije satelita u realnom vremenu sa N2YO API-ja
- **Klasifikacija po tipu misije** — Misije u bojama: vojno izviđanje (crveno), SAR (cijan), SIGINT (belo), navigacija (plavo), rano upozorenje (magenta), komercijalno snimanje (zeleno), svemirska stanica (zlatno)

###  Geopolitika i sukobi

- **Globalni incidenti** — GDELT agregacija konfliktnih događaja (poslednjih 8 sati, ~1.000 događaja)
- **Ukrajinska linija fronta** — Živi GeoJSON fronta sa DeepState Map
- **SIGINT/RISINT vest feed** — Agregacija RSS u realnom vremenu sa više izvora fokusiranih na obaveštajne podatke
- **Regionalni dosije** — Desni klik bilo gde na mapi za:
  - Profil države (stanovništvo, glavni grad, jezici, valute, površina)
  - Šef države i tip vlade (Wikidata SPARQL)
  - Lokalni Wikipedia sažetak sa sličicom

###  Nadzor

- **CCTV mreža** — 2.000+ živih kamera u saobraćaju sa:
  - 🇬🇧 Transport for London JamCams
  - 🇺🇸 Austin, TX TxDOT
  - 🇺🇸 NYC DOT
  - 🇸🇬 Singapore LTA
  - Unos prilagođenih URL-ova
- **Renderovanje izvora** — Automatska detekcija i prikaz video, MJPEG, HLS, embed, satelitskih tile i slikovnih izvora
- **Grupisani prikaz na mapi** — Zelene tačke se grupišu sa oznakama broja, razgrupišu se pri zumiranju

###  Signalna inteligencija

- **Detekcija GPS ometanja** — Analiza u realnom vremenu NAC-P (Navigation Accuracy Category) vrednosti letelica
  - Agregacija po mreži identifikuje zone interferencije
  - Crveni kvadrati preklapanja sa oznakama ozbiljnosti „GPS JAM XX%"
- **Panel presretanja radija** — Skenerski interfejs za praćenje komunikacija

###  Dodatni slojevi

- **Zemljotresi (24h)** — USGS feed zemljotresa u realnom vremenu sa markerima razmerne magnitude
- **Ciklus dan/noć** — Preklapanje solarnog terminatora prikazuje globalnu dnevnu svetlost/tamu
- **Tiker globalnih tržišta** — Živi indeksi finansijskih tržišta (može se minimizovati)
- **Alatka za merenje** — Merenje udaljenosti i azimuta od tačke do tačke na mapi

---

##  Arhitektura

```
┌──────────────────────────────────────────────────────┐
│                  FRONTEND (Next.js)                   │
│                                                      │
│  ┌─────────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │ MapLibre GL │  │ Tok vesti│  │ Kontrolni paneli│ │
│  │ 2D WebGL    │  │ SIGINT   │  │ Slojevi/Filteri │ │
│  │ Render mape │  │ Intel    │  │ Tržišta/Radio   │ │
│  └──────┬──────┘  └────┬─────┘  └────────┬────────┘ │
│         └──────────────┼─────────────────┘           │
│                        │ REST API (15s brzo / 60s)    │
├────────────────────────┼─────────────────────────────┤
│                  BACKEND (FastAPI)                    │
│                        │                              │
│  ┌─────────────────────┼─────────────────────────┐   │
│  │          Dobavljač podataka (Planer)          │   │
│  │  ┌──────────┬──────────┬──────────┬─────────┐ │   │
│  │  │ OpenSky  │ adsb.lol │  N2YO    │  USGS   │ │   │
│  │  │  Letovi  │  Vojni   │ Sateliti │ Potresi │ │   │
│  │  ├──────────┼──────────┼──────────┼─────────┤ │   │
│  │  │ AIS WS   │  Nosači  │  GDELT   │  CCTV   │ │   │
│  │  │ Brodovi  │ Praćenje │  Sukobi  │ Kamere  │ │   │
│  │  ├──────────┼──────────┼──────────┼─────────┤ │   │
│  │  │DeepState │   RSS    │  Regija  │   GPS   │ │   │
│  │  │  Front   │  Intel   │  Dosije  │Ometanje │ │   │
│  │  └──────────┴──────────┴──────────┴─────────┘ │   │
│  └───────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

---

##  Izvori podataka i API-ji

| Izvor | Podaci | Učestalost ažuriranja | Neophodan API ključ |
|---|---|---|---|
| [OpenSky Network](https://opensky-network.org) | Komercijalni i privatni letovi | ~60s | Opciono (anonimno, ograničeno) |
| [adsb.lol](https://adsb.lol) | Vojni avioni | ~60s | Ne |
| [aisstream.io](https://aisstream.io) | AIS pozicije plovila | WebSocket u realnom vremenu | **Da** |
| [N2YO](https://www.n2yo.com) | Orbitalne pozicije satelita | ~60s | **Da** |
| [USGS Earthquake](https://earthquake.usgs.gov) | Globalni seizmički događaji | ~60s | Ne |
| [GDELT Project](https://www.gdeltproject.org) | Globalni konfliktni događaji | ~6h | Ne |
| [DeepState Map](https://deepstatemap.live) | Ukrajinska linija fronta | ~30min | Ne |
| [Transport for London](https://api.tfl.gov.uk) | London CCTV JamCams | ~5min | Ne |
| [TxDOT](https://its.txdot.gov) | Kamere u saobraćaju, Austin TX | ~5min | Ne |
| [NYC DOT](https://webcams.nyctmc.org) | Kamere u saobraćaju, NYC | ~5min | Ne |
| [Singapore LTA](https://datamall.lta.gov.sg) | Kamere u saobraćaju, Singapur | ~5min | **Da** |
| [RestCountries](https://restcountries.com) | Profil podaci država | Na zahtev (keširano 24h) | Ne |
| [Wikidata SPARQL](https://query.wikidata.org) | Podaci o šefu države | Na zahtev (keširano 24h) | Ne |
| [Wikipedia API](https://en.wikipedia.org/api) | Sažeci lokacija i slike letelica | Na zahtev (keširano) | Ne |
| [CARTO Basemaps](https://carto.com) | Tamni map tiles | Kontinualno | Ne |

---


### 💻 Podešavanje za developere

Ako želite da menjate kod ili pokrenete iz izvora:

#### Preduslovi

- **Node.js** 18+ i **npm**
- **Python** 3.10+ sa `pip`-om
- API ključevi za: `aisstream.io`, `n2yo.com` (i opciono `opensky-network.org`, `lta.gov.sg`)

### Instalacija

```bash
# Klonirajte repozitorijum
git clone https://github.com/your-username/shadowbroker.git
cd shadowbroker/live-risk-dashboard

# Podešavanje backend-a
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# Kreirajte .env sa svojim API ključevima
echo "AISSTREAM_API_KEY=your_key_here" >> .env
echo "N2YO_API_KEY=your_key_here" >> .env
echo "OPENSKY_USERNAME=your_user" >> .env
echo "OPENSKY_PASSWORD=your_pass" >> .env

# Podešavanje frontend-a
cd ../frontend
npm install
```

### Pokretanje

```bash
# Iz direktorijuma frontend — istovremeno pokreće frontend i backend
npm run dev
```

Ovo pokreće:

- **Next.js** frontend na `http://localhost:3000`
- **FastAPI** backend na `http://localhost:8000`

---

##  Slojevi podataka

Svi slojevi se nezavisno uključuju/isključuju sa levog panela:

| Sloj | Podrazumevano | Opis |
|---|---|---|
| Komercijalni letovi | ✅ UKLJ | Avio-kompanije, teret, GA letelice |
| Privatni letovi | ✅ UKLJ | Nekomercijalne privatne letelice |
| Privatni džetovi | ✅ UKLJ | Poslovni džetovi više vrednosti sa podacima o vlasniku |
| Vojni letovi | ✅ UKLJ | Vojne i državne letelice |
| Praćene letelice | ✅ UKLJ | Specijalna lista posmatranja |
| Sateliti | ✅ UKLJ | Orbitalna sredstva po tipu misije |
| Nosaci / vojne / teretne | ✅ UKLJ | Mornarički nosači, teretni brodovi, tankeri |
| Civilna plovila | ❌ ISKLJ | Jahte, ribarstvo, rekreacija |
| Kruzeri / putnički | ✅ UKLJ | Kruzeri i trajekte |
| Zemljotresi (24h) | ✅ UKLJ | USGS seizmički događaji |
| CCTV mreža | ❌ ISKLJ | Mreža kamera nadzora |
| Ukrajinska linija fronta | ✅ UKLJ | Pozicije živog fronta |
| Globalni incidenti | ✅ UKLJ | GDELT konfliktni događaji |
| GPS ometanje | ✅ UKLJ | Zone NAC-P degradacije |
| Ciklus dan / noć | ✅ UKLJ | Preklapanje solarnog terminatora |

---

##  Performanse

Platforma je optimizovana za obrimu masu podataka u realnom vremenu:

- **Gzip kompresija** — API podaci kompresovani ~92% (11,6 MB → 915 KB)
- **ETag keširanje** — Odgovori `304 Not Modified` preskaču redundantno raščlanjivanje JSON-a
- **Odsecanje po viewportu** — Prikažu se samo objekti unutar vidljivih granica mape (+20% bafera)
- **Grupisano renderovanje** — Brodovi, CCTV i zemljotresi koriste MapLibre klasterizaciju radi smanjenja broja objekata
- **Odložena ažuriranja viewporta** — 300ms debounce sprečava nepotrebno pregrađivanje GeoJSON-a tokom pomeranja/zuma
- **Interpolacija pozicije** — Glatka animacija na 10s između osvežavanja podataka
- **React.memo** — Teške komponente su omotane radi sprečavanja nepotrebnih ponovnih renderovanja
- **Preciznost koordinata** — Lat/lng zaokruženi na 5 decimala (~1m) radi smanjenja veličine JSON-a

---

##  Struktura projekta

```
live-risk-dashboard/
├── backend/
│   ├── main.py                     # FastAPI aplikacija, midlver, API rute
│   ├── carrier_cache.json          # Trajne OSINT pozicije nosača
│   ├── cctv.db                     # SQLite baza CCTV kamera
│   └── services/
│       ├── data_fetcher.py         # Glavni planer — dovlaci sve izvore podataka
│       ├── ais_stream.py           # AIS WebSocket klijent (25K+ plovila)
│       ├── carrier_tracker.py      # OSINT pratioc pozicija nosača
│       ├── cctv_pipeline.py        # Unos CCTV kamera sa više izvora
│       ├── geopolitics.py          # Dovlačenje GDELT + ukrajinske linije fronta
│       ├── region_dossier.py       # Intel države/grada na desni klik
│       ├── radio_intercept.py      # Integracija skenerskog radio izvora
│       ├── network_utils.py        # HTTP klijent sa curl rezervom
│       └── api_settings.py         # Upravljanje API ključevima
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   └── page.tsx            # Glavni panel — stanje, upitivanje, raspored
│   │   └── components/
│   │       ├── MaplibreViewer.tsx   # Jezgro mape — 2.000+ redova, svi GeoJSON slojevi
│   │       ├── NewsFeed.tsx         # SIGINT izvor + paneli detalja entiteta
│   │       ├── WorldviewLeftPanel.tsx   # Prekidači slojeva podataka
│   │       ├── WorldviewRightPanel.tsx  # Panel za pretragu i filtere
│   │       ├── FilterPanel.tsx     # Osnovni filteri slojeva
│   │       ├── AdvancedFilterModal.tsx  # Filteri aerodrom/država/vlasnik
│   │       ├── MapLegend.tsx       # Dinamička legenda sa svim ikonama
│   │       ├── MarketsPanel.tsx    # Tiker globalnih finansijskih tržišta
│   │       ├── RadioInterceptPanel.tsx # Radio panel u skenerskom stilu
│   │       ├── FindLocateBar.tsx   # Traka za pretragu/lokalizaciju
│   │       ├── SettingsPanel.tsx   # Podešavanja aplikacije
│   │       ├── ScaleBar.tsx        # Indikator razmere mape
│   │       ├── WikiImage.tsx       # Dovlačenje Wikipedia slika
│   │       └── ErrorBoundary.tsx   # Omot za oporavak nakon pada
│   └── package.json
```

---

##  Promenljive okruženja

Kreirajte `.env` fajl u direktorijumu `backend/`:

```env
# Neophodni
AISSTREAM_API_KEY=your_aisstream_key      # Praćenje pomorskih plovila
N2YO_API_KEY=your_n2yo_key               # Podaci o pozicijama satelita

# Opcioni (poboljšavaju kvalitet podataka)
OPENSKY_CLIENT_ID=your_opensky_client_id  # Viši limiti za podatke o letovima
OPENSKY_CLIENT_SECRET=your_opensky_secret
LTA_ACCOUNT_KEY=your_lta_key             # CCTV kamere u Singapuru
```

---

## ⚠️ Odricanje od odgovornosti

Ovo je **obrazovni i istraživački alat** napravljen isključivo na javno dostupnim, otvorenim obaveštajnim (OSINT) podacima. Ne koriste se klasifikovani, ograničeni ili tajni izvori podataka. Pozicije nosača su procene zasnovane na javnom izveštavanju. Vojni izgled korisničkog interfejsa je isključivo estetski.

**Ne koristite ovaj alat u bilo koju operativnu, vojnu ili obaveštajnu svrhu.**

---

## Licenca

Pogledajte uslove korišćenja pojedinačnih API provajdera u vezi sa ograničenjima korišćenja podataka.

---

<p align="center">
  <sub>2026</sub>
</p>
