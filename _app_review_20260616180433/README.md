# Blue Cross U9's Android Native App

This is a Kotlin + Jetpack Compose Android-native starter port of the uploaded HTML app.

## What is implemented

- Native Compose UI: Dashboard, Teams, Participants, Assignments, Group Matches, Backup.
- Local persistence using `SharedPreferences` under the same key as the browser app: `worldcupSweepstake2026`.
- Fallback World Cup 2026 group data copied from the HTML app.
- WBCFC logo and `Mappings.csv` bundled as Android resources/assets.
- JSON backup export/import through Android document picker.

## What still needs porting from the HTML app

The uploaded browser app has a large amount of JavaScript logic. This starter ports the core local workflow, but these items still need to be implemented natively if you want full parity:

- Online team refresh from Wikipedia/public group pages.
- OpenFootball match result refresh and knockout result import.
- Group table calculation and leaderboard scoring rules.
- Knockout stages editor and winner progression.
- Winner odds and match odds import/fetch.
- Manual odds import parser.
- More detailed validation and aliases from the original `app.js`.

## Build

Open this folder in Android Studio and let Gradle sync. The project uses:

- Android Gradle Plugin `9.2.1`
- Kotlin / Compose Compiler plugin `2.3.21`
- Compose BOM `2026.05.01`
- compileSdk / targetSdk `37`

AGP 9.2 supports API level 37 and uses Gradle 9.4.1 / JDK 17 according to Android's 9.2 release notes.

## Next recommended steps

1. Run the app and confirm the local workflow matches what you need.
2. Port scoring/table functions from `app.js` into Kotlin unit-tested functions.
3. Add a repository layer for online updates using Kotlin coroutines and `HttpURLConnection` or OkHttp.
4. Add instrumented tests for import/export compatibility with existing browser backups.


## v1.1.57
- Leaderboard win chance now matches the Odds tab win chance exactly, using the API odds probability without group/knockout boosts.


## v1.1.18
- Fresh installs now seed participant names from the bundled Mappings.csv file.
- When bundled teams are available, participant/team assignments are also created automatically.


## v1.1.19
- Leaderboard headings remain frozen while vertically scrolling leaderboard rows.
- Participant column remains frozen while horizontally scrolling stat columns.


## v1.1.27
- Group Matches tab now shows each group as a collapsible section.

- v1.1.32 removes the redundant in-tab Group Matches heading.


## v1.1.43
- Match odds now use one bookmaker source per match and show that source under Home/Draw/Away odds.


## v1.1.43
- Odds description text now uses the same typography style as leaderboard rows.


## v1.1.56
- Updated Gradle versionCode/versionName so the footer displays the current app version.
