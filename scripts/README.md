# Mise à jour automatique du cockpit

Une tâche planifiée Claude tourne chaque matin :

1. Interroge le connecteur Meta Ads (Avinesh_Ads, compte 997654456068162, campagne UNPI69_P1_Trafic_LP) du 18/11/2026 jusqu'à la veille et colle les réponses dans `raw/` (daily, ads, ages, platforms, adsets, ads_list).
2. `python3 scripts/update_cockpit.py need-creatives --raw raw` liste les annonces dont le visuel n'est pas encore en cache ; leur `get_ad_creative` est passé à l'étape suivante.
3. `python3 scripts/update_cockpit.py build --raw raw --creative-files …` réécrit `data/meta.json`, `data/creatives.json`, `data/creative_index.json` et ajoute les visuels dans `assets/crea/ad_<id>.jpg`.
4. Commit + push sur `main` : Render redéploie le site.

GA4 reste chargé en direct depuis le cockpit (bouton « Charger GA4 en direct »).
