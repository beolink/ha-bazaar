# Roadmap för Bazaar, november 2026

Bazaar står på 0.1.4 (release 2026-11-10) och ligger på alla fem hus. Katalogen bygger varje natt och hade den 26 november 16 205 repon: 14 038 integrationer, 2 000 dashboardkort, 108 teman och 59 övriga, varav 924 med en öppen PR i hacs/default. Alla integrationer utom 217 (nedladdning eller arkiv föll) har fått sin kod läst; läsningen gav 54 höga, 670 medel och 544 låga flaggor. Filen är 9,0 MB okomprimerad. Integrationen talar med Marknadsplatsen i Home Assistant 2026.11 och med HACS före det, och lägger till repon utan att själv installera något. Testerna är 15 för integrationen och 30 för katalogen, alla gröna.

Två saker ramar in roadmapen. hacs/default stängde Bazaars PR (#14826) den 24 november av principskäl: en katalog över ogranskade repon ska inte stå i den granskade listan, hur noggrann koden än är. Bazaar fortsätter alltså som anpassat repo, och spridningen måste gå andra vägar. Och HA 2026.11 gjorde HACS till kärnkomponenten `marketplace`, vars websocket-API nu är det Bazaar ska bygga på; `dev` (2027.1) har samma kommandon och fält som 2026.11.3 plus två för kritiska repon, så API:et är stabilt för stunden.

Så togs roadmapen fram: en läsare gick igenom all kod (5 300 rader Python och JavaScript, tester, arbetsflöden och webbplats), Marknadsplatsens websocket-API i 2026.11.3 och i `dev`, och den skarpa katalogens siffror. Varje post bär sina belägg som fil och rad. Det var en genomgång med en läsare, inte flera perspektiv som i CTC-roadmapen, så den ska läsas som ett förslag att pröva, inte som en färdig prioritering.

| Fas | Poster | Vad fasen ger |
|---|---|---|
| Fas 0: beslut och prov | 3 | Ägaren väljer väg, och tilläggsflödet är provat i ett riktigt hus. |
| Fas 1: rätt och tryggt | 10 | Inget skrivs i onödan, panelen laddar inte om 9 MB varje gång, och testerna prövar det Bazaar faktiskt talar med. |
| Fas 2: Marknadsplatsen på riktigt | 5 | Panelen lyssnar i stället för att polla, visar vad butiken vet och förstår dess felkoder. |
| Fas 3: katalogen säger mer | 7 | Stängda PR:ar, köplats, utkast och vart koden ringer syns; fler repon hittas. |
| Fas 4: lätt och snabb | 2 | Katalogen går att använda på en telefon. |
| Fas 5: spridning och språk | 3 | Webbplatsen talar om Marknadsplatsen, fler språk, och en tydlig installationsväg utan HACS lista. |
| Längre sikt | 1 | Katalogkällor i Marknadsplatsen själv. |

Storlek per post: S är en kväll, M några kvällar, L en vecka eller mer.

## Fas 0: beslut och prov

### P1. Prova tilläggsflödet i ett riktigt hus (S)

Flödet "Lägg till i Marknadsplatsen" har bara provats mot en falsk `hass` (public/panel-test.html, numera borttagen), aldrig i en riktig 2026.11. Välj ett ofarligt repo och prova i ett hus: lägg till, se att det dyker upp i `known` inom de fem försöken, öppna sidan, ta bort det i Marknadsplatsen igen. Prova också de två spärrarna: varning inte godkänd och GitHub inte anslutet, som panelen ska visa som rutor med knappen "Öppna Marknadsplatsen".

Belägg: `custom_components/bazaar/frontend/bazaar-panel.js:315` till `:351` (`_add`), `:290` till `:294` (rutorna).

### P2. Svar till hacs/default och väg framåt (beslut)

PR #14826 stängdes med motiveringen att den granskade listan inte ska peka på en katalog över ogranskade repon. Ägaren avgör om och hur det besvaras, och om Bazaar ska föreslås som katalogkälla i Marknadsplatsens diskussionskategori (se F1). Svaret styr S3.

### P3. Hur länge HACS-vägen ska leva (beslut)

Panelen talar med HACS när Marknadsplatsen saknas, och testerna stubbar HACS. Home Assistant före 2026.11 lever länge i hemmen, så vägen bör finnas kvar minst till mitten av 2027. Beslut: sätt ett datum, och ta då bort `STORES.hacs`, stubben och texterna i ett svep.

Belägg: `bazaar-panel.js:10` till `:21`, `tests/stub_hacs/`.

## Fas 1: rätt och tryggt

### R1. Skriv inte om 9 MB var sjätte timme (S)

När katalogservern svarar 304 Not Modified bygger koordinatorn en ny `Catalog` av den gamla och sparar den ändå: `_async_save_cache` skriver `raw` (9 MB) och metafilen till `.storage` vid varje uppdatering, också när inget ändrats. På ett SD-kort är det fyra onödiga skrivningar om dygnet i varje hus. Spara bara metafilen (tiden för hämtningen) när svaret var 304.

Belägg: `custom_components/bazaar/coordinator.py:174` till `:185`.

### R2. Katalogvyn med ETag (S)

Panelen hämtar `/api/bazaar/catalog` med `Cache-Control: no-store`, så varje öppning av panelen laddar hela katalogen. Sätt `ETag` till katalogens egen ETag eller `generated`, svara 304 på `If-None-Match`, och låt webbläsaren cacha med `private, max-age=0, must-revalidate`. Hämtningen efter "Hämta katalogen igen" byter ETag av sig själv.

Belägg: `custom_components/bazaar/__init__.py:139` till `:159`, `coordinator.py:47`.

### R3. Testa mot Marknadsplatsen, inte bara HACS (M)

Testerna stubbar bara HACS (`tests/stub_hacs`), och `requirements-test.txt` är opinnad, så vilken Home Assistant testerna kör mot beror på dagen. Lägg till en stubb för `marketplace` med kommandona panelen använder (`marketplace/repositories/list`, `/add`, `marketplace/info`) och deras felkoder (`warning_not_accepted`, `github_not_connected`, `repository_exists`, `add_failed`), och pröva `store`-valet och tilläggsflödet mot den. Pinna Home Assistant-versionen i testerna så att en grön körning betyder något.

Belägg: `tests/conftest.py`, `tests/stub_hacs/custom_components/hacs/__init__.py`, `requirements-test.txt`, `__init__.py:111`. Marknadsplatsens felkoder: `homeassistant/components/marketplace/websocket/decorators.py:15` till `:19`, `websocket/repositories.py:231` till `:307`.

### R4. Veckokörning mot nästa Home Assistant (S)

`validate.yaml` kör redan varje måndag. Lägg till ett jobb som installerar nästa beta (`pip install --pre`) så att ett API-byte i Marknadsplatsen syns veckor före release, inte när husen uppgraderat. 2026.12 kommer i december och `dev` står redan på 2027.1.

Belägg: `.github/workflows/validate.yaml:7` till `:8`, `:31` till `:44`.

### R5. Släpp bara in ikoner från kända värdar (S)

`normalize()` godtar vilken `https://`-adress som helst som ikon. Katalogen kan komma från en adress användaren själv angett, och då kan varje kort ladda en bild från en okänd server, med användarens IP som gåva. Katalogbygget skapar bara adresser på `raw.githubusercontent.com` och `brands.home-assistant.io`, så begränsa till dem.

Belägg: `bazaar-catalog.js:469`, `catalog/collect.py:126` till `:132`.

### R6. Etiketten "report" finns inte (S)

Både panelen och webbplatsen öppnar ett ärende med `labels: report`, men repot har ingen sådan etikett (bara GitHubs standarduppsättning), så GitHub släpper parametern tyst och anmälningar går inte att filtrera. Skapa etiketten, med en beskrivning av vad en anmälan är.

Belägg: `bazaar-panel.js:192` till `:197`, `site/site.js:81` till `:88`.

### R7. Diagnostik (S)

Integrationen saknar `diagnostics.py`. Lägg till en som ger katalogens adress, `generated`, `fetched`, `counts`, vilken butik som hittades, senaste felet och versionen. Det är vad ett felärende behöver och vad `bazaar/info` redan räknar fram.

Belägg: `__init__.py:100` till `:113` (`_info`), ingen `diagnostics.py` i `custom_components/bazaar/`.

### R8. Ett Repair när ingen butik finns (S)

Saknas både Marknadsplatsen och HACS visar panelen en röd ruta, men bara när någon öppnar den. Skapa ett Repair-ärende vid `async_setup_entry` när ingen av dem är laddad, och ta bort det när en dyker upp. Då syns det under Inställningar som allt annat som behöver åtgärd.

Belägg: `__init__.py:54` till `:78`, `:111`; `bazaar-panel.js:290`.

### R9. En version på ett ställe (S)

`VERSION` i `const.py` och `version` i `manifest.json` måste stämma överens, och panelens cache-brytare (`?v=`) läser den förra. Ett test som jämför dem räcker.

Belägg: `custom_components/bazaar/const.py:7`, `manifest.json:20`, `__init__.py:74`.

### R10. Tester för panelen (M)

1 371 rader JavaScript utan automatiska tester. Pröva `normalize()` mot en katalog med fel typer, `_filtered()` mot filter och sortering, och tilläggsflödet mot en falsk `hass` vars `callWS` spelar både Marknadsplats och HACS, inklusive felkoderna i R3. `node:test` med jsdom räcker; ingen webbläsare behövs.

Belägg: `bazaar-catalog.js:450` till `:509`, `:621` till `:646`; `bazaar-panel.js:236` till `:264`, `:315` till `:351`.

### R11. Nattjobbet säger till när det haltar (S)

Går `CATALOG_TOKEN` ut faller jobbet tillbaka på arbetsflödets egen token, kodsökningen nekas, katalogen märks `incomplete` och fyller på med gårdagens namn, natt efter natt, utan att någon får veta. Låt ett steg öppna ett ärende (eller fälla jobbet) när `incomplete` är satt två nätter i rad, och lägg tokenens utgångsdatum i en kommentar i arbetsflödet.

Belägg: `.github/workflows/catalog.yml:9` till `:12`, `:56` till `:60`; `catalog/collect.py:344` till `:360`.

## Fas 2: Marknadsplatsen på riktigt

### M1. Lyssna i stället för att polla (S)

Efter `marketplace/repositories/add` hämtar panelen hela listan upp till fem gånger med en sekunds paus för att se när repot dykt upp. Marknadsplatsen har `marketplace/subscribe` med signalen `marketplace_repository`, som skickas när ett repo ändras. Prenumerera när panelen öppnas, uppdatera `known` på händelsen, och visa installation och uppdatering i realtid medan användaren är kvar i Bazaar.

Belägg: `bazaar-panel.js:329` till `:335`; `homeassistant/components/marketplace/websocket/__init__.py:65` till `:102`; `enums.py:21` till `:29`.

### M2. Visa vad butiken vet (S)

`repositories/list` ger per repo `installed`, `installed_version`, `available_version`, `pending_upgrade`, `new`, `status` och `can_install`. Panelen använder bara `id` och `installed`. Visa "Uppdatering finns" med version, "Ny" tills användaren öppnat det, och gråa ut knappen när `can_install` är falskt.

Belägg: `bazaar-panel.js:244`, `bazaar-catalog.js:817` till `:820`; `websocket/repositories.py:28` till `:59`.

### M3. Fråga butiken om kategorin före tillägg (M)

Katalogens kategori kommer ur `analyze.classify`, en gissning ur mappstrukturen. Marknadsplatsen har `marketplace/repositories/detect {repository}` som svarar med de kategorier repot faktiskt har innehåll för. Anropa den i bekräftelsedialogen; stämmer de inte överens, erbjud butikens kategori i stället för att låta `add` falla med `add_failed`. Kräver godkänd varning och GitHub, precis som `add`.

Belägg: `catalog/analyze.py:53` till `:101`; `websocket/repositories.py:152` till `:208`.

### M4. Handla på felkoden, inte bara texten (S)

Marknadsplatsen svarar med kod och översatt text. Panelen visar texten, vilket är rätt, men kan göra mer: vid `repository_exists` uppdatera `known` och öppna repots sida (någon annan lade till det), vid `warning_not_accepted` eller `github_not_connected` gå till `/marketplace` i stället för en toast. `marketplace/warning/accept` finns men ska aldrig anropas av Bazaar: varningen är användarens att läsa.

Belägg: `bazaar-panel.js:336` till `:350`; `websocket/decorators.py:15` till `:19`; `websocket/repositories.py:257` till `:265`.

### M5. Kategorier Marknadsplatsen saknar (S)

Marknadsplatsen installerar integration, plugin, template och theme; AppDaemon (50 repon) och Python-skript (6) går inte att lägga till, vilket panelen redan visar med ett kryss. Överväg att dölja dem som standard i panelen på 2026.11, eller att lämna dem ur katalogen helt när HACS-vägen stängs (P3).

Belägg: `bazaar-panel.js:262`, `bazaar-catalog.js:589` till `:591`, `:821` till `:822`; `marketplace/enums.py:7` till `:13`.

## Fas 3: katalogen säger mer

Ett villkor för hela fasen: `schema: 1` är ett löfte. `parse_catalog` i varje installerad Bazaar förkastar en katalog med annat schemanummer och sitter kvar på sin cache för gott, så nya fält läggs till, inga tas bort eller byter mening. `normalize()` i panelen släpper redan okända fält förbi.

Belägg: `coordinator.py:58` till `:59`, `bazaar-catalog.js:450` till `:509`.

### K1. Stängda PR:ar (L)

Kön läses bara ur öppna PR:ar (`states: OPEN`). Ett repo vars PR stängdes utan sammanslagning, och det finns över sex tusen sådana PR:ar i hacs/default, visas i dag som "Inte inskickat", vilket är fel och döljer det mest talande en användare kan få veta. Läs också stängda, ej sammanslagna PR:ar (en gång fullt, sedan bara de som ändrats sedan förra natten), och ge varje repo ett `submission`-fält: `open`, `draft`, `closed` med datum och länk till PR:en så att läsaren själv ser om det var begärda ändringar, inaktivitet eller författaren. Statusfiltret får fyra lägen: i kön, utkast, stängd, aldrig inskickad. Finns både en stängd och en öppen PR vinner den öppna, som i dag.

Belägg: `catalog/sources.py:88` till `:105`, `:149` till `:181`; `bazaar-catalog.js:29` till `:30`, `:627` till `:628`.

### K2. Köplats och utkast (M)

HACS kö är de öppna PR:ar som inte är utkast, äldst först; ett utkast står utanför. Katalogen räknar alla öppna PR:ar som "i kön" (924), fast många är utkast. Hämta `isDraft`, räkna varje icke-utkasts plats, och visa "Plats 212 av 413 i kön" respektive "Utkast, utanför kön". Sorteringen "Längst i kön" ska gå på platsen.

Belägg: `catalog/sources.py:91` till `:100` (frågan saknar `isDraft`); `bazaar-catalog.js:641`, `:803` till `:806`.

### K3. Vart koden ringer (M)

Kodläsningen flaggar farliga mönster men säger inget om vart en integration pratar. Samla strängkonstanter som är `http(s)://`-adresser, och visa de skilda värdarna som en upplysning, inte en flagga: "Pratar med api.leverantor.com". GitHub, brands.home-assistant.io och lokala adresser (192.168., 10., .local) räknas inte. En molnintegration utan molnvärd i koden är också värd en blick.

Belägg: `catalog/scan.py:62` till `:117` (`_scan_tree`), konstantgrenen `:112` till `:116`.

### K4. Skriver utanför sin mapp (M)

En ny regel på medelnivå: skrivning (`open(..., "w")`, `write_text`, `write_bytes`, `shutil.copy`) till en sökväg som bildas av `hass.config.path(...)` med `.storage`, `www`, `custom_components` eller `secrets.yaml`, eller till absoluta sökvägar utanför `/config`. Tillsammans med `ha-credentials` täcker det de två sätten en integration kan göra skada i stillhet.

Belägg: `catalog/scan.py:27` till `:39` (reglerna), `tests/test_catalog.py:272` (mönstret för nya regeltester).

### K5. Fler källor än kodsökningen (M)

Kodsökningen (tio anrop i minuten, 45 % av nattens budget) missar nya repon i veckor, därav `include.json`. GitHubs reposökning på ämnen (`topic:hacs`, `topic:hacs-integration`, `topic:home-assistant-integration`) ger hundra repon per anrop vid trettio i minuten och indexeras snabbare. Lägg den som andra källa; samma kontroller avgör som i dag.

Belägg: `catalog/sources.py:216` till `:238`, `catalog/collect.py:343` till `:362`, `include.json`.

### K6. Inaktiva repon (S)

691 repon har inte fått en push sedan 2023. Poängen straffar dem, men inget filter skiljer ut dem. Lägg till filtret "Uppdaterat senaste året" och en diskret "inaktiv"-märkning över två år.

Belägg: `catalog/analyze.py:161` till `:163`, `bazaar-catalog.js:692` till `:695`.

### K7. Visa vem krocken gäller (S)

2 166 repon delar domän med något annat repo i katalogen, och texten säger bara hur många. Gör märkningen klickbar så att den söker på domänen (sökfältet täcker redan `domain`), så ser användaren de andra kopiorna och kan välja original.

Belägg: `bazaar-catalog.js:565` (`_hay`), `:866`.

## Fas 4: lätt och snabb

### L1. Mät panelen på en telefon (S, före L2)

Katalogen är 9,0 MB JSON som webbläsaren tolkar och håller i minnet, och varje tangenttryck (efter 120 ms) filtrerar 16 205 poster. Det går på en dator; hur det går i följeslagarappen på en telefon vet ingen. Mät tid till första lista, minne och sökfördröjning på en iPhone och en äldre Android innan något byggs om.

Belägg: `bazaar-catalog.js:11`, `:559` till `:567`, `:621` till `:646`, `:706` till `:709`.

### L2. Ett slankt index och detaljer vid behov (L, om L1 kräver det)

Dela katalogen i `index.json` med det listan behöver (repo, namn, kategori, stjärnor, poäng, flaggornas antal per nivå, kö, krock, uppdaterad, release, ikon) och detaljer per repo (beskrivning, kontroller, flaggor med rader, ämnen) som hämtas när ett kort fälls ut. Integrationen hämtar och cachar indexet som i dag och proxar detaljerna med samma inloggning. Webbplatsen kan hämta detaljerna direkt från Pages. `schema: 1` behålls för `catalog.json` så länge 0.1.x-installationer finns kvar (se villkoret i Fas 3).

Belägg: `catalog/collect.py:189` till `:217` (`for_clients`), `const.py:15` (`MAX_CATALOG_BYTES`), `coordinator.py:63` till `:82`.

## Fas 5: spridning och språk

### S1. Webbplatsen talar fortfarande om HACS (S)

"Så fungerar det" säger att "Öppna i HACS" tar dig till Home Assistant och att HACS frågar, och knappen heter "Lägg till Bazaar i HACS", på båda språken. Panelen byttes till Marknadsplatsen i 0.1.4, men inte webbplatsen. Skriv om punkt 4 och panelrutan: Marknadsplatsen i 2026.11 och senare, HACS före det. My-länken fungerar via frontendens omdirigering.

Belägg: `site/index.html:51`, `:58`, `:60`; `site/site.js:24` till `:29`.

### S2. Fler språk i panelen (M)

Panelens texter ligger i JavaScript på engelska och svenska, och Home Assistants egna översättningar täcker bara inställningsflödet. Lägg texterna i en JSON-fil per språk som laddas efter `hass.locale`, och börja med tyska, nederländska, franska och spanska, de största Home Assistant-språken efter engelska. Översättningarna kan tas emot som PR:ar när strukturen finns.

Belägg: `bazaar-catalog.js:19` till `:214`, `bazaar-panel.js:23` till `:64`, `custom_components/bazaar/translations/`.

### S3. En tydlig installationsväg utan HACS lista (S, efter P2)

Sedan #14826 stängdes är vägen in det anpassade repot: My-länken i README och webbplatsen, eller adressen inklistrad under "Anpassade repon" i Marknadsplatsen. Skriv steget med Marknadsplatsens ord och en skärmbild, säg öppet att HACS valt att inte lista Bazaar och varför, och lägg sedan ut Bazaar där Home Assistant-användare letar (forumets "Share your projects", r/homeassistant) när ägaren bestämt det (P2). Repot har i dag noll stjärnor och 18 unika klonare på två veckor; ingen hittar det på egen hand.

Belägg: `README.md:31` till `:43`, `site/index.html:55` till `:61`.

## Längre sikt

### F1. Katalogkällor i Marknadsplatsen själv (beslut, sedan förslag)

Marknadsplatsen läser en enda katalog, `hacs/default`. Supervisorn har sedan länge motsatsen för tillägg: vem som helst kan publicera ett "add-on repository", användaren klistrar in adressen, och butiken visar innehållet med en varning. Samma modell för Marknadsplatsen, en katalogkälla som en URL med samma schema som `data-v2.hacs.xyz`, skulle göra Bazaar till en källa bland flera och ta bort behovet av en egen panel. Det är den rätta långsiktiga platsen för idén, och ett förslag i Marknadsplatsens diskussionskategori (github.com/orgs/home-assistant/discussions, kategorin Marketplace) kostar lite. Bazaars `catalog.json` kan då få en systerfil i det schemat.

Belägg: `homeassistant/components/marketplace/const.py:43` (`CATALOG_REPOSITORY = "hacs/default"`), `data_client.py:24` till `:60`.

## Prövat och struket

- **Installera direkt från Bazaar** (`marketplace/repository/install`). Nej. Att Bazaar aldrig installerar är en bärande princip i README, i panelens dialog och i det som sades till HACS; den gör också att Marknadsplatsens egna varning och GitHub-krav alltid gäller.
- **Godkänna Marknadsplatsens varning åt användaren** (`marketplace/warning/accept`). Nej. Varningen finns för att läsas.
- **Skicka användningsstatistik** till stats.rnet.se som de andra integrationerna. Nej. "Skickar inget" är ett löfte i README och var ett argument för katalogen; GitHub Pages har ingen räknare, och det får vara så.
- **Läsa dashboardkortens JavaScript** som integrationernas Python. Inte nu. 2 000 kort, byggd och ofta minifierad kod; en syntaxträdsläsning av JavaScript är ett eget projekt med osäker träffsäkerhet. Kandidat för senare, med `eval(`, `new Function(` och `fetch(` till främmande värdar som första regler.
- **Ta bort HACS-vägen nu.** För tidigt; se P3.
- **Virtuell rullning i listan.** Sextio per sida med "Visa fler" räcker tills L1 visar annat.
