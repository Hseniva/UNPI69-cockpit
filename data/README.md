# Données du cockpit

- `meta.json` : performance Meta Ads (compte UNPI 69, act_997654456068162) depuis le lancement. Rafraîchi à partir du connecteur Meta Ads, puis publié (Render redéploie à chaque push sur `main`).
- `ga4.json` : relevé GA4 (propriété 519433339, G-17FSE1Z4S9). Le bouton « Charger GA4 en direct » interroge GA4 avec le compte Google de la personne connectée.
- `creatives.json` + `assets/crea/` : visuels carrés des 5 annonces principales.

Champs de `meta.json` : `daily[]` (date, spend, impressions, reach, link_clicks, lpv, leads, partial), `themes[]`, `ads[]`, `ages[]`, `platforms[]`, `budget`, `benchmark`, `updated_at`.
