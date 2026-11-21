# Dimensional Chaos — Translations

Traductions du mod **Dimensional Chaos** et du livre de quêtes du modpack **Dimensional Chaos - OneBlock**.
*English below.*

## Aider à traduire (pas besoin de GitHub)

1. Ouvrez la page Crowdin du projet : **lien bientôt disponible**.
2. Connectez-vous (compte Crowdin gratuit, ou avec Google, GitHub, etc.) et choisissez votre langue.
3. Traduisez les textes directement dans le navigateur. Vous voyez le texte anglais à côté de chaque ligne.

Vos traductions sont relues puis intégrées à la prochaine version du mod et du modpack.

Quelques règles :
- Gardez tels quels les `%s`, `%d`, `%1$s` et `%%` : le jeu les remplace par un nom, un nombre…
- Gardez les noms propres du pack (Dimensional Chaos, OneBlock) et les noms d'objets tels qu'ils apparaissent en jeu
  dans votre langue.
- Une langue manque ? Demandez-la sur la page Crowdin ou dans les [issues du pack](https://github.com/ShyzosCorp/Dimensional-Chaos-Issues/issues).

## Ce qui est traduit ici

| Dossier | Contenu |
|---|---|
| `source/mod/en_us.json` | Textes du mod (messages, objets, écrans) — anglais, ne pas modifier |
| `source/quests/en_us.json` | Livre de quêtes — anglais, ne pas modifier |
| `translations/<partie>/<langue>.json` | Une traduction par langue (`fr_fr`, `pl_pl`, `zh_cn`…), écrite par Crowdin |

Les traductions des autres mods du pack ne sont pas ici : leurs textes appartiennent à leurs auteurs.

## Comment ça marche

Les textes anglais viennent du dépôt du mod. Crowdin propose chaque nouvelle traduction ici dans une pull request ;
une vérification automatique contrôle chaque fichier (JSON valide, clés connues, `%s` conservés). Les traductions
validées sont intégrées au mod à chaque nouvelle version.

En proposant une traduction, vous acceptez qu'elle soit distribuée avec Dimensional Chaos et son modpack.

---

## Help translate (no GitHub needed)

1. Open the project's Crowdin page: **link coming soon**.
2. Sign in (free Crowdin account, or with Google, GitHub…) and pick your language.
3. Translate in your browser, with the English text next to each line.

Translations are reviewed and shipped with the next version of the mod and the modpack.

- Keep `%s`, `%d`, `%1$s` and `%%` exactly as they are: the game replaces them with a name, a number…
- Keep the pack's names (Dimensional Chaos, OneBlock) and use item names as the game shows them in your language.
- Missing language? Ask on the Crowdin page or in the [pack's issues](https://github.com/ShyzosCorp/Dimensional-Chaos-Issues/issues).

`source/` holds the English texts (do not edit), `translations/<part>/<language>.json` one file per language, written by
Crowdin. Other mods' translations are not here: their texts belong to their authors. Every change is checked
automatically (valid JSON, known keys, placeholders kept), then merged into the mod at the next release.

By submitting a translation you agree that it is distributed with Dimensional Chaos and its modpack.
