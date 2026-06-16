package com.wbcfc.worldcupsweepstake

import android.app.Activity
import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.pow
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.runtime.LaunchedEffect
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.rememberDrawerState
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.material3.MenuAnchorType

private const val STORAGE_KEY = "worldcupSweepstake2026"
private const val FOOTBALL_DATA_API_KEY = "e55437fb579f45778f3a950203819976"
private const val FOOTBALL_DATA_MATCHES_URL = "https://api.football-data.org/v4/competitions/WC/matches"
private val GROUPS = "ABCDEFGHIJKL".toList().map { it.toString() }
private val KNOCKOUT_STAGES = listOf("Last 32", "Last 16", "Quarter-finals", "Semi-finals", "Third Place Playoff", "Final")
private val WbcBlue = Color(0xFF062967)
private val WbcBlueDark = Color(0xFF041D4A)
private val WbcBackground = Color(0xFFF5F7FA)
private val WbcSurface = Color.White
private val WbcOnPrimary = Color.White
private val WbcOnSurface = Color(0xFF1A1A1A)
private val WbcColorScheme = lightColorScheme(
    primary = WbcBlue,
    onPrimary = WbcOnPrimary,
    secondary = WbcBlueDark,
    onSecondary = WbcOnPrimary,
    background = WbcBackground,
    onBackground = WbcOnSurface,
    surface = WbcSurface,
    onSurface = WbcOnSurface,
    primaryContainer = WbcBlueDark,
    onPrimaryContainer = WbcOnPrimary,
    secondaryContainer = Color(0xFFE8EEF8),
    onSecondaryContainer = WbcBlueDark
)
private val FALLBACK_GROUPS = mapOf(
    "A" to listOf("Mexico", "South Africa", "South Korea", "Czechia"),
    "B" to listOf("Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"),
    "C" to listOf("Brazil", "Morocco", "Haiti", "Scotland"),
    "D" to listOf("United States", "Paraguay", "Australia", "Turkey"),
    "E" to listOf("Germany", "Curaçao", "Ivory Coast", "Ecuador"),
    "F" to listOf("Netherlands", "Japan", "Sweden", "Tunisia"),
    "G" to listOf("Belgium", "Egypt", "Iran", "New Zealand"),
    "H" to listOf("Spain", "Cape Verde", "Saudi Arabia", "Uruguay"),
    "I" to listOf("France", "Senegal", "Iraq", "Norway"),
    "J" to listOf("Argentina", "Algeria", "Austria", "Jordan"),
    "K" to listOf("Portugal", "DR Congo", "Uzbekistan", "Colombia"),
    "L" to listOf("England", "Croatia", "Ghana", "Panama")
)

private fun uuid() = UUID.randomUUID().toString()
private fun norm(s: String?) = (s ?: "").lowercase().replace("&", " and ").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
private fun displayTeamName(name: String?) = when (norm(name)) {
    "usa", "u s a", "united states of america" -> "United States"
    "czech republic" -> "Czechia"
    "south korea", "korea republic", "republic of korea", "korea south" -> "South Korea"
    "iran" -> "IR Iran"
    "turkiye", "tuerkiye" -> "Turkey"
    "bosnia herzegovina", "bosnia and herzegovina" -> "Bosnia and Herzegovina"
    "cote d ivoire", "cote divoire" -> "Ivory Coast"
    "curacao" -> "Curaçao"
    "d r congo", "congo dr", "democratic republic of the congo" -> "DR Congo"
    "cape verde islands" -> "Cape Verde"
    else -> (name ?: "").trim().replace(Regex("^The ", RegexOption.IGNORE_CASE), "")
}

private fun sourceNameToAppName(name: String?) = displayTeamName(name)

data class Team(val id: String = uuid(), val name: String = "", val group: String)
data class Participant(val id: String = uuid(), val name: String)
data class Assignment(val id: String = uuid(), val participantId: String, val teamId: String)
data class Match(
    val id: String = uuid(), val stage: String = "Group", val group: String = "", val round: Int = 1,
    val homeId: String = "", val awayId: String = "", val homeSlot: Int = 0, val awaySlot: Int = 0,
    val homeScore: Int? = null, val awayScore: Int? = null, val complete: Boolean = false,
    val date: String = "", val time: String = "", val ground: String = ""
)
data class KnockoutMatch(
    val id: String = uuid(), val stage: String = "Last 32", val homeId: String = "", val awayId: String = "",
    val homeName: String = "TBC", val awayName: String = "TBC", val homeScore: Int? = null, val awayScore: Int? = null,
    val winnerId: String = "", val complete: Boolean = false, val date: String = "", val time: String = "", val ground: String = "", val sourceKey: String = ""
)
data class OddsEntry(val teamName: String, val decimal: Double, val fractional: String = decimalToFractional(decimal), val source: String = "Manual")
data class MatchOddsEntry(val homeDecimal: Double? = null, val drawDecimal: Double? = null, val awayDecimal: Double? = null, val source: String = "The Odds API")
data class SweepstakeState(
    val teams: List<Team> = defaultTeams(),
    val participants: List<Participant> = emptyList(),
    val assignments: List<Assignment> = emptyList(),
    val matches: List<Match> = generateFixtures(defaultTeams()),
    val knockoutMatches: List<KnockoutMatch> = emptyList(),
    val odds: Map<String, OddsEntry> = emptyMap(),
    val matchOdds: Map<String, MatchOddsEntry> = emptyMap(),
    val teamSource: String = "",
    val matchSource: String = "",
    val oddsSource: String = ""
)

private fun defaultTeams() = GROUPS.flatMap { group -> (1..4).map { Team(group = group) } }
private fun fallbackTeams() = GROUPS.flatMap { group -> FALLBACK_GROUPS[group].orEmpty().map { Team(name = it, group = group) } }
private fun generateFixtures(teams: List<Team>): List<Match> = teams.groupBy { it.group }.flatMap { (group, groupTeams) ->
    val t = groupTeams.take(4)
    listOf(0 to 1, 2 to 3, 0 to 2, 1 to 3, 0 to 3, 1 to 2).mapIndexedNotNull { index, (a, b) ->
        if (t.size > b) Match(group = group, round = index / 2 + 1, homeId = t[a].id, awayId = t[b].id, homeSlot = a + 1, awaySlot = b + 1) else null
    }
}

class Store(private val context: Context) {
    private val prefs = context.getSharedPreferences("sweepstake", Context.MODE_PRIVATE)
    fun load(): SweepstakeState = runCatching {
        val raw = prefs.getString(STORAGE_KEY, null)
        if (raw.isNullOrBlank()) {
            val seeded = seededInitialState(context)
            save(seeded)
            return seeded
        }
        val loaded = stateFromJson(JSONObject(raw))
        if (loaded.participants.isEmpty()) {
            val seeded = seedParticipantsAndAssignments(context, loaded)
            save(seeded)
            seeded
        } else {
            loaded
        }
    }.getOrElse { seededInitialState(context) }
    fun save(state: SweepstakeState) = prefs.edit().putString(STORAGE_KEY, state.toJson().toString(2)).apply()
}

private fun seededInitialState(context: Context): SweepstakeState {
    val teams = fallbackTeams()
    val base = SweepstakeState(
        teams = teams,
        matches = generateFixtures(teams),
        teamSource = "Bundled World Cup Sweepstake snapshot"
    )
    return seedParticipantsAndAssignments(context, base)
}

private fun seedParticipantsAndAssignments(context: Context, state: SweepstakeState): SweepstakeState {
    val csv = runCatching {
        context.assets.open("Mappings.csv").bufferedReader().use { it.readText() }
    }.getOrNull().orEmpty()
    return if (csv.isBlank()) state else applyMappingsCsv(state, csv)
}

private fun stateFromJson(root: JSONObject): SweepstakeState {
    val teams = root.optJSONArray("teams").toTeams().ifEmpty { defaultTeams() }
    val matches = root.optJSONArray("matches").toMatches().ifEmpty { generateFixtures(teams) }
    return SweepstakeState(
        teams = teams,
        participants = root.optJSONArray("participants").toParticipants(),
        assignments = root.optJSONArray("assignments").toAssignments(),
        matches = matches,
        knockoutMatches = root.optJSONArray("knockoutMatches").toKnockouts(),
        odds = root.optJSONObject("odds").toOdds(),
        matchOdds = root.optJSONObject("matchOdds").toMatchOdds(),
        teamSource = root.optJSONObject("teamSource")?.optString("name") ?: root.optString("teamSource"),
        matchSource = root.optJSONObject("matchSource")?.optString("name") ?: root.optString("matchSource"),
        oddsSource = root.optString("oddsSource")
    )
}
private fun JSONArray?.toTeams() = (0 until (this?.length() ?: 0)).mapNotNull { i -> this?.optJSONObject(i)?.let { Team(it.optString("id", uuid()), displayTeamName(it.optString("name")), it.optString("group")) } }
private fun JSONArray?.toParticipants() = (0 until (this?.length() ?: 0)).mapNotNull { i -> this?.optJSONObject(i)?.let { Participant(it.optString("id", uuid()), it.optString("name")) } }
private fun JSONArray?.toAssignments() = (0 until (this?.length() ?: 0)).mapNotNull { i -> this?.optJSONObject(i)?.let { Assignment(it.optString("id", uuid()), it.optString("participantId"), it.optString("teamId")) } }
private fun JSONArray?.toMatches() = (0 until (this?.length() ?: 0)).mapNotNull { i -> this?.optJSONObject(i)?.let { o -> Match(o.optString("id", uuid()), o.optString("stage", "Group"), o.optString("group"), o.optInt("round", 1), o.optString("homeId", o.optString("homeTeamId")), o.optString("awayId", o.optString("awayTeamId")), o.optInt("homeSlot"), o.optInt("awaySlot"), o.optNullableInt("homeScore"), o.optNullableInt("awayScore"), o.optBoolean("complete", o.hasScores()), o.optString("date"), o.optString("time"), o.optString("ground")) } }
private fun JSONArray?.toKnockouts() = (0 until (this?.length() ?: 0)).mapNotNull { i -> this?.optJSONObject(i)?.let { o -> KnockoutMatch(o.optString("id", uuid()), o.optString("stage"), o.optString("homeId", o.optString("homeTeamId")), o.optString("awayId", o.optString("awayTeamId")), o.optString("homeName", o.optString("homeTeamSourceName", "TBC")), o.optString("awayName", o.optString("awayTeamSourceName", "TBC")), o.optNullableInt("homeScore"), o.optNullableInt("awayScore"), o.optString("winnerId", o.optString("winnerTeamId")), o.optBoolean("complete", o.hasScores()), o.optString("date"), o.optString("time"), o.optString("ground"), o.optString("sourceKey")) } }
private fun JSONObject?.toOdds(): Map<String, OddsEntry> {
    if (this == null) return emptyMap()
    val out = linkedMapOf<String, OddsEntry>()
    keys().forEach { key ->
        val v = opt(key)
        val entry = if (v is JSONObject) OddsEntry(v.optString("teamName", key), v.optDouble("decimal", 0.0), v.optString("fractional", ""), v.optString("source", "Imported")) else OddsEntry(key, valueToDecimal(v) ?: 0.0)
        if (entry.decimal > 1) out[norm(entry.teamName)] = entry
    }
    return out
}
private fun JSONObject?.toMatchOdds(): Map<String, MatchOddsEntry> {
    if (this == null) return emptyMap()
    val out = linkedMapOf<String, MatchOddsEntry>()
    keys().forEach { key ->
        val v = optJSONObject(key) ?: return@forEach
        out[key] = MatchOddsEntry(
            homeDecimal = v.optNullableDouble("homeDecimal"),
            drawDecimal = v.optNullableDouble("drawDecimal"),
            awayDecimal = v.optNullableDouble("awayDecimal"),
            source = v.optString("source", "The Odds API")
        )
    }
    return out
}
private fun JSONObject.optNullableDouble(name: String) = if (has(name) && !isNull(name) && optString(name).isNotBlank()) optDouble(name) else null
private fun JSONObject.optNullableInt(name: String) = if (has(name) && !isNull(name) && optString(name).isNotBlank()) optInt(name) else null
private fun JSONObject.hasScores() = optNullableInt("homeScore") != null && optNullableInt("awayScore") != null
private fun SweepstakeState.toJson() = JSONObject().apply {
    put("teams", JSONArray(teams.map { JSONObject().put("id", it.id).put("name", it.name).put("group", it.group) }))
    put("participants", JSONArray(participants.map { JSONObject().put("id", it.id).put("name", it.name) }))
    put("assignments", JSONArray(assignments.map { JSONObject().put("id", it.id).put("participantId", it.participantId).put("teamId", it.teamId) }))
    put("matches", JSONArray(matches.map { JSONObject().put("id", it.id).put("stage", it.stage).put("group", it.group).put("round", it.round).put("homeTeamId", it.homeId).put("awayTeamId", it.awayId).put("homeSlot", it.homeSlot).put("awaySlot", it.awaySlot).put("homeScore", it.homeScore).put("awayScore", it.awayScore).put("complete", it.complete).put("date", it.date).put("time", it.time).put("ground", it.ground) }))
    put("knockoutMatches", JSONArray(knockoutMatches.map { JSONObject().put("id", it.id).put("stage", it.stage).put("homeTeamId", it.homeId).put("awayTeamId", it.awayId).put("homeTeamSourceName", it.homeName).put("awayTeamSourceName", it.awayName).put("homeScore", it.homeScore).put("awayScore", it.awayScore).put("winnerTeamId", it.winnerId).put("complete", it.complete).put("date", it.date).put("time", it.time).put("ground", it.ground).put("sourceKey", it.sourceKey) }))
    put("odds", JSONObject().apply { odds.forEach { (k, v) -> put(k, JSONObject().put("teamName", v.teamName).put("decimal", v.decimal).put("fractional", v.fractional).put("source", v.source)) } })
    put("matchOdds", JSONObject().apply { matchOdds.forEach { (k, v) -> put(k, JSONObject().put("homeDecimal", v.homeDecimal).put("drawDecimal", v.drawDecimal).put("awayDecimal", v.awayDecimal).put("source", v.source)) } })
    put("teamSource", teamSource); put("matchSource", matchSource); put("oddsSource", oddsSource)
}

class MainActivity : ComponentActivity() { override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); setContent { App(Store(this)) } } }

private val tabs = listOf("Dashboard", "Participants", "Assignments", "Groups", "Group Matches", "Knockout", "Odds", "Backup")

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun App(store: Store) {
    var state by remember { mutableStateOf(store.load()) }
    var tab by remember { mutableStateOf("Dashboard") }
    var status by remember { mutableStateOf("") }
    val context = LocalContext.current
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()

    fun update(next: SweepstakeState) {
        state = next
        store.save(next)
    }

    LaunchedEffect(Unit) {
        runAsync(
            context,
            { fetchFootballData(state) },
            { nextState ->
                update(nextState)
                status = "Fixtures/results updated online."
            },
            { error ->
                status = "Match update failed: ${error.message}"
            }
        )
    }

    MaterialTheme(colorScheme = WbcColorScheme) {
        ModalNavigationDrawer(
            drawerState = drawerState,
            drawerContent = {
                ModalDrawerSheet {
                    Text(
                        text = "Menu",
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(16.dp)
                    )
                    tabs.forEach { item ->
                        NavigationDrawerItem(
                            label = { Text(item) },
                            selected = tab == item,
                            onClick = {
                                tab = item
                                scope.launch { drawerState.close() }
                            },
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 2.dp)
                        )
                    }
                }
            }
        ) {
            Scaffold(
                containerColor = MaterialTheme.colorScheme.background,
                topBar = {
                    TopAppBar(
                        
                        title = {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Image(
                                    painter = painterResource(R.drawable.wbcfc_logo),
                                    contentDescription = "Wootton Blue Cross logo",
                                    modifier = Modifier.size(32.dp)
                                )
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    text = "Blue Cross U9's",
                                    maxLines = 1,
                                    softWrap = false,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        },
                        actions = {
                            IconButton(onClick = { scope.launch { drawerState.open() } }) {
                                Icon(
                                    Icons.Default.Menu,
                                    contentDescription = "Open menu",
                                    tint = Color.White
                                )
                            }
                        },
                        colors = TopAppBarDefaults.topAppBarColors(
                            containerColor = WbcBlue,
                            titleContentColor = Color.White
                        )
                    )
                },
                bottomBar = {
                    Surface(color = WbcBlue, contentColor = Color.White) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(8.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "World Cup Sweepstake 2026 • v${BuildConfig.VERSION_NAME}",
                                style = MaterialTheme.typography.bodySmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }
            ) { padding ->
                Column(Modifier.padding(padding).fillMaxSize()) {
                    Header(
                        state,
                        status,
                        onUpdateTeams = {
                            runAsync(
                                context,
                                { fetchWorldCupGroups() },
                                { groups ->
                                    val ns = applyGroupsToState(state, groups, "Wikipedia live group pages")
                                    update(ns)
                                    status = "Teams updated online."
                                },
                                { status = "Team update failed: ${it.message}" }
                            )
                        },
                        onUpdateMatches = {
                            runAsync(
                                context,
                                { fetchFootballData(state) },
                                { ns ->
                                    update(ns)
                                    status = "Fixtures/results updated online."
                                },
                                { status = "Match update failed: ${it.message}" }
                            )
                        }
                    )

                    when (tab) {
                        "Dashboard" -> Dashboard(state)
                        "Participants" -> Participants(state) { update(it) }
                        "Assignments" -> Assignments(state) { update(it) }
                        "Groups" -> GroupsScreen(state)
                        "Group Matches" -> Matches(state) { update(it) }
                        "Knockout" -> Knockout(state) { update(it) }
                        "Odds" -> Odds(state) { update(it) }
                        "Backup" -> Backup(state) { update(it) }
                    }
                }
            }
        }
    }
}

@Composable fun Header(state: SweepstakeState, status: String, onUpdateTeams: () -> Unit, onUpdateMatches: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.surface) {
    Column(Modifier.fillMaxWidth().padding(12.dp)) {
        Column(Modifier.fillMaxWidth()) {
            Text(
                text = "World Cup Sweepstake",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.height(4.dp))
            Text("${state.teams.count { it.name.isNotBlank() }} teams")
            Text("${state.participants.size} participants")
            Text("${state.matches.count { it.complete }} results")
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onUpdateTeams) { Text("Resync Teams") }
            OutlinedButton(onClick = onUpdateMatches) { Text("Update fixtures/results") }
        }
        if (status.isNotBlank()) Text(status, style = MaterialTheme.typography.bodySmall)
    }
    }
}

@Composable fun Dashboard(state: SweepstakeState) {
    val standingsByTeam = GROUPS
        .flatMap { standingsForGroup(state, it) }
        .associateBy { it.teamId }

    val ranked = state.assignments.mapNotNull { assignment ->
        val participant = state.participants.find { it.id == assignment.participantId } ?: return@mapNotNull null
        val team = state.teams.find { it.id == assignment.teamId } ?: return@mapNotNull null
        val standing = standingsByTeam[team.id] ?: Standing(team.id, team.name.ifBlank { "Unnamed team" })
        LeaderboardRow(
            participant = participant.name,
            team = team.name.ifBlank { "Unnamed team" },
            knockoutRank = knockoutStageRank(state, team.id),
            groupPts = standing.pts,
            groupGd = standing.gd,
            wins = standing.w,
            draws = standing.d,
            losses = standing.l,
            winChance = bookmakerChance(state, team.id)
        )
    }.sortedWith(
        compareByDescending<LeaderboardRow> { it.knockoutRank }
            .thenByDescending { it.groupPts }
            .thenByDescending { it.groupGd }
            .thenBy { it.participant }
    )

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Leaderboard", style = MaterialTheme.typography.headlineSmall)
        if (ranked.isEmpty()) {
            Text("Add participants and assignments to show the leaderboard.", modifier = Modifier.padding(top = 8.dp))
        } else {
            LeaderboardTable(ranked, modifier = Modifier.weight(1f))
        }
    }
}

private fun knockoutStageRank(state: SweepstakeState, teamId: String): Int {
    val match = state.knockoutMatches
        .filter { it.homeId == teamId || it.awayId == teamId || it.winnerId == teamId }
        .maxByOrNull {
            when (it.stage) {
                "Final" -> 6
                "Semi-finals" -> 5
                "Quarter-finals" -> 4
                "Last 16" -> 3
                "Last 32" -> 2
                else -> 1
            }
        }
    return when (match?.stage) {
        "Final" -> 6
        "Semi-finals" -> 5
        "Quarter-finals" -> 4
        "Last 16" -> 3
        "Last 32" -> 2
        else -> 1
    }
}

data class LeaderboardRow(
    val participant: String,
    val team: String,
    val knockoutRank: Int,
    val groupPts: Int,
    val groupGd: Int,
    val wins: Int,
    val draws: Int,
    val losses: Int,
    val winChance: Double
)

@Composable fun LeaderboardTable(rows: List<LeaderboardRow>, modifier: Modifier = Modifier) {
    val horizontalScroll = rememberScrollState()
    val participantWidth = 100
    val rowHeight = 36.dp
    val headerHeight = 40.dp

    Column(modifier.fillMaxWidth().padding(top = 8.dp)) {
        Row(Modifier.fillMaxWidth().height(headerHeight)) {
            LeaderboardCell("Participant", participantWidth, height = headerHeight, bold = true)
            Row(Modifier.weight(1f).horizontalScroll(horizontalScroll)) {
                LeaderboardCell("Team", 132, height = headerHeight, bold = true)
                LeaderboardCell("Group Pts", 104, height = headerHeight, bold = true)
                LeaderboardCell("Wins", 76, height = headerHeight, bold = true)
                LeaderboardCell("Draws", 84, height = headerHeight, bold = true)
                LeaderboardCell("Losses", 84, height = headerHeight, bold = true)
                LeaderboardCell("Win Chance", 120, height = headerHeight, bold = true)
            }
        }

        LazyColumn(Modifier.fillMaxSize()) {
            items(rows, key = { it.participant + "|" + it.team }) { row ->
                Row(Modifier.fillMaxWidth().height(rowHeight)) {
                    LeaderboardCell(row.participant, participantWidth, height = rowHeight)
                    Row(Modifier.weight(1f).horizontalScroll(horizontalScroll)) {
                        LeaderboardCell(row.team, 132, height = rowHeight)
                        LeaderboardCell(row.groupPts.toString(), 104, height = rowHeight)
                        LeaderboardCell(row.wins.toString(), 76, height = rowHeight)
                        LeaderboardCell(row.draws.toString(), 84, height = rowHeight)
                        LeaderboardCell(row.losses.toString(), 84, height = rowHeight)
                        LeaderboardCell("${(row.winChance * 100).format(1)}%", 120, height = rowHeight)
                    }
                }
            }
        }
    }
}

@Composable fun LeaderboardCell(text: String, width: Int, height: Dp, bold: Boolean = false) {
    Box(
        modifier = Modifier
            .width(width.dp)
            .height(height)
            .padding(end = 8.dp),
        contentAlignment = Alignment.CenterStart
    ) {
        Text(
            text = text,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            softWrap = false,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable fun Teams(state: SweepstakeState, update: (SweepstakeState) -> Unit) = LazyColumn(Modifier.padding(16.dp)) {
    GROUPS.forEach { group ->
        item { Text("Group $group", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 12.dp)) }
        items(state.teams.filter { it.group == group }, key = { it.id }) { team ->
            var name by remember(team.id, team.name) { mutableStateOf(team.name) }
            OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Team") }, modifier = Modifier.fillMaxWidth(), singleLine = true, trailingIcon = { TextButton(onClick = { update(state.copy(teams = state.teams.map { if (it.id == team.id) it.copy(name = displayTeamName(name)) else it })) }) { Text("Save") } })
        }
    }
}

private val SweepstakeInputHeight = 48.dp
private val SweepstakeInputTextStyle
    @Composable get() = MaterialTheme.typography.bodyMedium

@Composable fun Participants(state: SweepstakeState, update: (SweepstakeState) -> Unit) {
    var name by remember { mutableStateOf("") }
    val participantRowHeight = 36.dp

    LazyColumn(Modifier.padding(16.dp)) {
        item {
            Row(Modifier.padding(bottom = 8.dp)) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(participantRowHeight)
                        .border(
                            BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                            MaterialTheme.shapes.extraSmall
                        )
                        .padding(horizontal = 8.dp),
                    contentAlignment = Alignment.CenterStart
                ) {
                    BasicTextField(
                        value = name,
                        onValueChange = { name = it },
                        singleLine = true,
                        textStyle = MaterialTheme.typography.bodySmall.copy(
                            color = MaterialTheme.colorScheme.onSurface
                        ),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        modifier = Modifier.fillMaxWidth(),
                        decorationBox = { innerTextField ->
                            if (name.isBlank()) {
                                Text(
                                    text = "Participant name",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    maxLines = 1
                                )
                            }
                            innerTextField()
                        }
                    )
                }
                Spacer(Modifier.width(8.dp))
                Button(modifier = Modifier.height(participantRowHeight), onClick = {
                    if (name.isNotBlank()) {
                        update(state.copy(participants = state.participants + Participant(name = name.trim())))
                        name = ""
                    }
                }) { Text("Add") }
            }
        }

        items(state.participants, key = { it.id }) { p ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(participantRowHeight),
                verticalAlignment = Alignment.CenterVertically
            ) {
                BasicTextField(
                    value = p.name,
                    onValueChange = { newName ->
                        update(
                            state.copy(
                                participants = state.participants.map {
                                    if (it.id == p.id) it.copy(name = newName) else it
                                }
                            )
                        )
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(participantRowHeight)
                        .padding(end = 8.dp)
                        .border(1.dp, MaterialTheme.colorScheme.outline, MaterialTheme.shapes.extraSmall),
                    singleLine = true,
                    textStyle = MaterialTheme.typography.bodySmall.copy(color = MaterialTheme.colorScheme.onSurface),
                    decorationBox = { innerTextField ->
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(horizontal = 8.dp),
                            contentAlignment = Alignment.CenterStart
                        ) {
                            innerTextField()
                        }
                    }
                )
                IconButton(
                    modifier = Modifier.size(participantRowHeight),
                    onClick = {
                        update(
                            state.copy(
                                participants = state.participants.filterNot { it.id == p.id },
                                assignments = state.assignments.filterNot { it.participantId == p.id }
                            )
                        )
                    }
                ) { Icon(Icons.Default.Delete, null) }
            }
        }
    }
}

@Composable fun Assignments(state: SweepstakeState, update: (SweepstakeState) -> Unit) { var participantId by remember { mutableStateOf("") }; var teamId by remember { mutableStateOf("") }; LazyColumn(Modifier.padding(16.dp)) { item { Text("Add assignment", style = MaterialTheme.typography.titleLarge) }; item { Dropdown("Participant", state.participants.map { it.id to it.name }, participantId) { participantId = it } }; item { Dropdown("Team", state.teams.filter { it.name.isNotBlank() }.map { it.id to "${it.name} (Group ${it.group})" }, teamId) { teamId = it } }; item { Button(onClick = { if (participantId.isNotBlank() && teamId.isNotBlank()) update(state.copy(assignments = state.assignments.filterNot { it.participantId == participantId || it.teamId == teamId } + Assignment(participantId = participantId, teamId = teamId))) }) { Text("Assign") } }; items(state.assignments, key = { it.id }) { a -> val p = state.participants.find { it.id == a.participantId }?.name.orEmpty(); val t = state.teams.find { it.id == a.teamId }?.name.orEmpty(); ListItem(headlineContent = { Text(p) }, supportingContent = { Text(t) }, trailingContent = { IconButton(onClick = { update(state.copy(assignments = state.assignments.filterNot { it.id == a.id })) }) { Icon(Icons.Default.Delete, null) } }) } } }

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun Dropdown(label: String, values: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val selectedText = values.firstOrNull { it.first == selected }?.second.orEmpty()
    val displayText = selectedText.ifBlank { label }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded },
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
    ) {
        Box(
            modifier = Modifier
                .menuAnchor(type = MenuAnchorType.PrimaryNotEditable, enabled = true)
                .fillMaxWidth()
                .height(36.dp)
                .border(
                    BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                    MaterialTheme.shapes.extraSmall
                )
                .padding(horizontal = 8.dp),
            contentAlignment = Alignment.CenterStart
        ) {
            Text(
                text = displayText,
                style = MaterialTheme.typography.bodySmall,
                color = if (selectedText.isBlank()) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
                maxLines = 1,
                softWrap = false,
                overflow = TextOverflow.Ellipsis
            )
        }

        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false }
        ) {
            values.forEach {
                DropdownMenuItem(
                    text = {
                        Text(
                            text = it.second,
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    },
                    onClick = {
                        onSelect(it.first)
                        expanded = false
                    }
                )
            }
        }
    }
}

@Composable fun GroupsScreen(state: SweepstakeState) = LazyColumn(Modifier.padding(12.dp)) {
    GROUPS.forEach { group ->
        item {
            Text("Group $group", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 12.dp))
            GroupTable(standingsForGroup(state, group))
        }
    }
}

@Composable fun GroupTable(rows: List<Standing>) {
    val scrollState = rememberScrollState()
    val teamWidth = 150.dp
    val statWidth = 48.dp
    val headerHeight = 36.dp
    val rowHeight = 34.dp

    Column(Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            GroupCell("Team", teamWidth, headerHeight, bold = true)
            Row(Modifier.horizontalScroll(scrollState), verticalAlignment = Alignment.CenterVertically) {
                listOf("P", "W", "D", "L", "GF", "GA", "GD", "Pts").forEach { heading ->
                    GroupCell(heading, statWidth, headerHeight, bold = true)
                }
            }
        }

        rows.forEach { row ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                GroupCell(row.team, teamWidth, rowHeight)
                Row(Modifier.horizontalScroll(scrollState), verticalAlignment = Alignment.CenterVertically) {
                    listOf(row.p, row.w, row.d, row.l, row.gf, row.ga, row.gd, row.pts).forEach { value ->
                        GroupCell(value.toString(), statWidth, rowHeight)
                    }
                }
            }
        }
    }
}

@Composable fun GroupCell(text: String, width: Dp, height: Dp, bold: Boolean = false) {
    Box(
        modifier = Modifier
            .width(width)
            .height(height)
            .padding(end = 8.dp),
        contentAlignment = Alignment.CenterStart
    ) {
        Text(
            text = text,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            softWrap = false,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable fun Matches(state: SweepstakeState, update: (SweepstakeState) -> Unit) {
    val expandedGroups = remember { mutableStateMapOf<String, Boolean>() }
    val matchesByGroup = remember(state.matches) { state.matches.groupBy { it.group }.toSortedMap() }

    LazyColumn(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        GROUPS.forEach { group ->
            val groupMatches = matchesByGroup[group].orEmpty()
            if (groupMatches.isNotEmpty()) {
                item(key = "group-$group") {
                    val expanded = expandedGroups[group] ?: false

                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        OutlinedButton(
                            onClick = { expandedGroups[group] = !expanded },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = if (expanded) "Group $group  ▾" else "Group $group  ▸",
                                fontWeight = FontWeight.Bold
                            )
                        }

                        if (expanded) {
                            groupMatches.forEach { m ->
                                MatchEditorRow(
                                    state = state,
                                    match = m,
                                    update = update
                                )
                                HorizontalDivider()
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable fun ReadOnlyScoreBox(score: Int?) {
    OutlinedCard(
        modifier = Modifier
            .width(70.dp)
            .height(48.dp)
    ) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            Text(score?.toString() ?: "-")
        }
    }
}

private fun matchOddsKey(homeName: String, awayName: String) = "${norm(homeName)}|${norm(awayName)}"
private fun swapped(entry: MatchOddsEntry) = MatchOddsEntry(entry.awayDecimal, entry.drawDecimal, entry.homeDecimal, entry.source)
private fun matchOddsFor(state: SweepstakeState, homeId: String, awayId: String, fallbackHome: String = "", fallbackAway: String = ""): MatchOddsEntry? {
    val home = if (homeId.isNotBlank()) teamName(state, homeId) else fallbackHome
    val away = if (awayId.isNotBlank()) teamName(state, awayId) else fallbackAway
    if (home.isBlank() || away.isBlank() || home == "TBC" || away == "TBC") return null
    val direct = state.matchOdds[matchOddsKey(home, away)]
    if (direct != null) return direct
    return state.matchOdds[matchOddsKey(away, home)]?.let { swapped(it) }
}
private fun oddsDisplay(decimal: Double?): String = decimal?.takeIf { it > 1.0 }?.let { decimalToFractional(it) } ?: "N/A"

@Composable
fun MatchOddsBlock(
    odds: MatchOddsEntry?,
    homeLabel: String = "Home",
    awayLabel: String = "Away"
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 4.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        Text(
            text = "$homeLabel win: ${oddsDisplay(odds?.homeDecimal)}",
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            softWrap = false,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = "Draw: ${oddsDisplay(odds?.drawDecimal)}",
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            softWrap = false,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = "$awayLabel win: ${oddsDisplay(odds?.awayDecimal)}",
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            softWrap = false,
            overflow = TextOverflow.Ellipsis
        )
        Text(
            text = "Source: ${odds?.source?.takeIf { it.isNotBlank() } ?: "N/A"}",
            style = MaterialTheme.typography.bodySmall
        )
    }
}

private fun participantNameForTeam(state: SweepstakeState, teamId: String): String {
    if (teamId.isBlank()) return "TBC"
    val assignment = state.assignments.firstOrNull { it.teamId == teamId } ?: return "TBC"
    return state.participants.firstOrNull { it.id == assignment.participantId }?.name?.ifBlank { "TBC" } ?: "TBC"
}

@Composable
private fun MatchParticipantsLine(state: SweepstakeState, homeId: String, awayId: String) {
    Text(
        text = "(${participantNameForTeam(state, homeId)} vs ${participantNameForTeam(state, awayId)})",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        maxLines = 1,
        softWrap = false,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable fun MatchEditorRow(state: SweepstakeState, match: Match, update: (SweepstakeState) -> Unit) {
    val home = teamName(state, match.homeId)
    val away = teamName(state, match.awayId)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
    ) {
        Text("$home v $away", fontWeight = FontWeight.Bold)
        MatchParticipantsLine(state, match.homeId, match.awayId)
        if (match.date.isNotBlank() || match.ground.isNotBlank()) {
            Text(
                listOf(match.date, match.time, match.ground).filter { it.isNotBlank() }.joinToString(" · "),
                style = MaterialTheme.typography.bodySmall
            )
        }
        MatchOddsBlock(odds = matchOddsFor(state, match.homeId, match.awayId), homeLabel = home, awayLabel = away)
        Row(verticalAlignment = Alignment.CenterVertically) {
            ReadOnlyScoreBox(match.homeScore)
            Text(" - ", modifier = Modifier.padding(horizontal = 6.dp))
            ReadOnlyScoreBox(match.awayScore)
        }
    }
}

@Composable fun Knockout(state: SweepstakeState, update: (SweepstakeState) -> Unit) {
    val currentStage = remember(state.knockoutMatches) { currentKnockoutStage(state) }
    var expandedStages by remember(state.knockoutMatches) {
        mutableStateOf(currentStage?.let { setOf(it) } ?: emptySet())
    }

    LazyColumn(
        modifier = Modifier.padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        KNOCKOUT_STAGES.forEach { stage ->
            val rows = state.knockoutMatches.filter { it.stage == stage }
            if (rows.isNotEmpty()) {
                item(key = "knockout-stage-$stage") {
                    val expanded = stage in expandedStages

                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                expandedStages = if (expanded) expandedStages - stage else expandedStages + stage
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = if (expanded) "$stage  ▾" else "$stage  ▸",
                                fontWeight = FontWeight.Bold
                            )
                        }

                        if (expanded) {
                            rows.forEach { m ->
                                val home = if (m.homeId.isNotBlank()) teamName(state, m.homeId) else m.homeName
                                val away = if (m.awayId.isNotBlank()) teamName(state, m.awayId) else m.awayName
                                Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                                    Text("$home v $away", fontWeight = FontWeight.Bold)
                                    MatchParticipantsLine(state, m.homeId, m.awayId)
                                    if (m.date.isNotBlank() || m.ground.isNotBlank()) {
                                        Text(
                                            listOf(m.date, m.time, m.ground).filter { it.isNotBlank() }.joinToString(" · "),
                                            style = MaterialTheme.typography.bodySmall
                                        )
                                    }
                                    MatchOddsBlock(odds = matchOddsFor(state, m.homeId, m.awayId, m.homeName, m.awayName), homeLabel = home, awayLabel = away)
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        ReadOnlyScoreBox(m.homeScore)
                                        Text(" - ", modifier = Modifier.padding(horizontal = 6.dp))
                                        ReadOnlyScoreBox(m.awayScore)
                                    }
                                }
                                HorizontalDivider()
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun currentKnockoutStage(state: SweepstakeState): String? {
    return KNOCKOUT_STAGES.firstOrNull { stage ->
        val rows = state.knockoutMatches.filter { it.stage == stage }
        rows.isNotEmpty() && rows.any { !it.complete }
    } ?: KNOCKOUT_STAGES.firstOrNull { stage -> state.knockoutMatches.any { it.stage == stage } }
}

private fun currentTimestamp(): String = SimpleDateFormat("dd MMM yyyy HH:mm", Locale.getDefault()).format(Date())

@Composable fun Odds(state: SweepstakeState, update: (SweepstakeState) -> Unit) {
    val context = LocalContext.current
    var status by remember { mutableStateOf("") }
    val oddsScrollState = rememberScrollState()

    LazyColumn(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Text("Odds", style = MaterialTheme.typography.headlineSmall)
            Button(onClick = {
                val key = BuildConfig.ODDS_API_KEY.trim()
                if (key.isBlank() || key == "PUT_YOUR_ODDS_API_KEY_HERE") {
                    status = "Odds API key is not configured in the app build."
                } else {
                    status = "Fetching odds…"
                    runAsync(context, { fetchTheOddsApiOdds(state.copy(odds = emptyMap(), matchOdds = emptyMap()), key) }, { next ->
                        update(next.copy(oddsSource = currentTimestamp()))
                        status = ""
                    }, { err -> status = "Odds API fetch failed: ${err.message}" })
                }
            }) { Text("Refresh odds") }
            Text(
                text = "Last updated: ${state.oddsSource.takeIf { it.isNotBlank() } ?: "Never"}",
                style = MaterialTheme.typography.bodySmall
            )
            if (status.isNotBlank()) Text(status, style = MaterialTheme.typography.bodySmall)
        }
        item {
            OddsTableHeader(oddsScrollState)
        }
        val sortedTeams = state.teams
            .filter { it.name.isNotBlank() }
            .sortedBy { it.name.lowercase() }
        items(sortedTeams, key = { it.id }) { team ->
            val entry = state.odds[norm(team.name)]
            OddsTableRow(
                scrollState = oddsScrollState,
                team = team.name,
                winnerOdds = entry?.fractional?.ifBlank { decimalToFractional(entry.decimal) } ?: "—",
                winChance = if (entry != null) "${(bookmakerChance(state, team.id) * 100).format(1)}%" else "—",
                source = entry?.source ?: "No API odds returned yet"
            )
        }
    }
}

@Composable
private fun OddsTableHeader(scrollState: androidx.compose.foundation.ScrollState) {
    val headerHeight = 40.dp
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp).height(headerHeight),
        verticalAlignment = Alignment.CenterVertically
    ) {
        OddsCell("Team", 130.dp, height = headerHeight, bold = true)
        Row(modifier = Modifier.weight(1f).horizontalScroll(scrollState)) {
            OddsCell("Winner odds", 105.dp, height = headerHeight, bold = true)
            OddsCell("Win chance", 105.dp, height = headerHeight, bold = true)
            OddsCell("Source", 190.dp, height = headerHeight, bold = true)
        }
    }
}

@Composable
private fun OddsTableRow(scrollState: androidx.compose.foundation.ScrollState, team: String, winnerOdds: String, winChance: String, source: String) {
    val rowHeight = 36.dp
    Row(
        modifier = Modifier.fillMaxWidth().height(rowHeight),
        verticalAlignment = Alignment.CenterVertically
    ) {
        OddsCell(team, 130.dp, height = rowHeight, bold = true)
        Row(modifier = Modifier.weight(1f).horizontalScroll(scrollState)) {
            OddsCell(winnerOdds, 105.dp, height = rowHeight)
            OddsCell(winChance, 105.dp, height = rowHeight)
            OddsCell(source, 190.dp, height = rowHeight)
        }
    }
}

@Composable
private fun OddsCell(text: String, width: Dp, height: Dp, bold: Boolean = false) {
    Box(
        modifier = Modifier
            .width(width)
            .height(height)
            .padding(end = 8.dp),
        contentAlignment = Alignment.CenterStart
    ) {
        Text(
            text = text,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            softWrap = false,
            overflow = TextOverflow.Ellipsis
        )
    }
}

@Composable fun Backup(state: SweepstakeState, update: (SweepstakeState) -> Unit) { val context = LocalContext.current; val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri -> uri?.let { context.contentResolver.openOutputStream(it)?.use { out -> out.write(state.toJson().toString(2).toByteArray()) } } }; val importJson = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { context.contentResolver.openInputStream(it)?.bufferedReader()?.use { reader -> update(stateFromJson(JSONObject(reader.readText()))) } } }; val importMap = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { context.contentResolver.openInputStream(it)?.bufferedReader()?.use { reader -> update(applyMappingsCsv(state, reader.readText())) } } }; Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) { Text("Backup / import", style = MaterialTheme.typography.headlineSmall); Button(onClick = { export.launch("worldcup-sweepstake-backup.json") }) { Text("Export backup") }; OutlinedButton(onClick = { importJson.launch(arrayOf("application/json", "text/*", "*/*")) }) { Text("Import backup JSON") }; OutlinedButton(onClick = { importMap.launch(arrayOf("text/*", "text/csv", "*/*")) }) { Text("Import team/participant mappings CSV") }; Text("Compatible with browser app JSON where possible: teams, participants, assignments, matches, knockoutMatches and odds.") } }

@Composable fun TableHeader(values: List<String>) { Row(Modifier.horizontalScroll(rememberScrollState()).padding(vertical = 3.dp)) { values.forEach { Text(it, Modifier.width(if (it == "Team") 150.dp else 44.dp), fontWeight = FontWeight.Bold) } } }
@Composable fun TableRow(values: List<String>) { Row(Modifier.horizontalScroll(rememberScrollState()).padding(vertical = 2.dp)) { values.forEachIndexed { i, v -> Text(v, Modifier.width(if (i == 0) 150.dp else 44.dp)) } } }

data class Standing(val teamId: String, val team: String, var p: Int = 0, var w: Int = 0, var d: Int = 0, var l: Int = 0, var gf: Int = 0, var ga: Int = 0, var gd: Int = 0, var pts: Int = 0)
private fun standingsForGroup(state: SweepstakeState, group: String): List<Standing> { val rows = state.teams.filter { it.group == group }.map { Standing(it.id, it.name.ifBlank { "Unnamed team" }) }; val byId = rows.associateBy { it.teamId }; state.matches.filter { it.group == group && it.complete }.forEach { m -> val h = byId[m.homeId] ?: return@forEach; val a = byId[m.awayId] ?: return@forEach; val hs = m.homeScore ?: return@forEach; val ascore = m.awayScore ?: return@forEach; h.p++; a.p++; h.gf += hs; h.ga += ascore; a.gf += ascore; a.ga += hs; if (hs > ascore) { h.w++; a.l++; h.pts += 3 } else if (ascore > hs) { a.w++; h.l++; a.pts += 3 } else { h.d++; a.d++; h.pts++; a.pts++ } }; rows.forEach { it.gd = it.gf - it.ga }; return rows.sortedWith(compareByDescending<Standing> { it.pts }.thenByDescending { it.gd }.thenByDescending { it.gf }.thenBy { it.team }) }
private fun groupComplete(state: SweepstakeState, group: String) = state.matches.count { it.group == group && it.complete } >= 6
private fun teamEliminated(state: SweepstakeState, teamId: String): Boolean { val team = state.teams.find { it.id == teamId } ?: return false; if (groupComplete(state, team.group) && standingsForGroup(state, team.group).takeLast(2).any { it.teamId == teamId }) return true; return state.knockoutMatches.any { it.complete && (it.homeId == teamId || it.awayId == teamId) && it.winnerId.isNotBlank() && it.winnerId != teamId } }
private fun bookmakerChance(state: SweepstakeState, teamId: String): Double { val team = state.teams.find { it.id == teamId } ?: return 0.0; val dec = state.odds[norm(team.name)]?.decimal ?: return 0.0; return 1.0 / dec }
private fun winnerFor(m: KnockoutMatch) = if (m.winnerId.isNotBlank()) m.winnerId else when { (m.homeScore ?: -1) > (m.awayScore ?: -1) -> m.homeId; (m.awayScore ?: -1) > (m.homeScore ?: -1) -> m.awayId; else -> "" }

private fun canonicalTeamNameForAssignment(name: String): String {
    val cleaned = displayTeamName(name)
        .lowercase()
        .replace("&", "and")
        .replace(".", "")
        .replace("-", " ")
        .replace(Regex("\\s+"), " ")
        .trim()

    return when (cleaned) {
        "czech republic", "czech rep", "czechia" -> "czechia"
        "cabo verde", "cape verde" -> "cape verde"
        "curacao", "curaçao" -> "curacao"
        "ivory coast", "cote divoire", "côte divoire", "côte d ivoire", "cote d ivoire" -> "ivory coast"
        "dr congo", "d r congo", "congo dr", "democratic republic of congo", "democratic republic of the congo" -> "dr congo"
        "usa", "united states", "united states of america" -> "united states"
        "south korea", "korea republic", "republic of korea" -> "south korea"
        else -> cleaned
    }
}

private fun preserveAssignmentsForUpdatedTeams(
    oldTeams: List<Team>,
    newTeams: List<Team>,
    assignments: List<Assignment>
): List<Assignment> {
    if (assignments.isEmpty()) return assignments

    val newTeamByCanonicalName = newTeams.associateBy { canonicalTeamNameForAssignment(it.name) }

    return assignments.mapNotNull { assignment ->
        val oldTeam = oldTeams.firstOrNull { it.id == assignment.teamId }
        val replacementTeam = oldTeam?.let { newTeamByCanonicalName[canonicalTeamNameForAssignment(it.name)] }

        when {
            replacementTeam != null -> assignment.copy(teamId = replacementTeam.id)
            newTeams.any { it.id == assignment.teamId } -> assignment
            else -> null
        }
    }.distinctBy { it.participantId to it.teamId }
}

fun applyGroupsToState(
    state: SweepstakeState,
    groups: Map<String, List<String>>,
    source: String
): SweepstakeState {
    val oldByName = state.teams
        .filter { it.name.isNotBlank() }
        .associateBy { canonicalTeamNameForAssignment(it.name) }

    val nextTeams = GROUPS.flatMap { group ->
        (groups[group].orEmpty().take(4) + List(4) { "" }).take(4).map { name ->
            val displayName = displayTeamName(name)
            oldByName[canonicalTeamNameForAssignment(displayName)]?.copy(
                name = displayName,
                group = group
            ) ?: Team(name = displayName, group = group)
        }
    }

    val preservedAssignments = preserveAssignmentsForUpdatedTeams(
        oldTeams = state.teams,
        newTeams = nextTeams,
        assignments = state.assignments
    )

    return state.copy(
        teams = nextTeams,
        matches = generateFixtures(nextTeams),
        assignments = preservedAssignments,
        teamSource = source
    )
}

private fun fetchWorldCupGroups(): Map<String, List<String>> { val out = linkedMapOf<String, List<String>>(); GROUPS.forEach { g -> val text = httpGet("https://en.wikipedia.org/api/rest_v1/page/summary/2026_FIFA_World_Cup_Group_$g"); val extract = JSONObject(text).optString("extract"); val found = Regex("consists of ([^.]+)\\.", RegexOption.IGNORE_CASE).find(extract)?.groupValues?.get(1) ?: error("Could not read Group $g"); val names = found.replace(Regex("\\(co-host\\)", RegexOption.IGNORE_CASE), "").replace(Regex(",?\\s+and\\s+([^,]+)$", RegexOption.IGNORE_CASE), ", $1").split(',').map { displayTeamName(it.trim()) }.filter { it.isNotBlank() }.take(4); if (names.size != 4) error("Group $g returned ${names.size} teams"); out[g] = names }; return out }

private fun normaliseFootballDataName(value: String): String =
    displayTeamName(value)
        .lowercase()
        .replace("the ", "")
        .replace("&", "and")
        .replace(".", "")
        .replace("-", " ")
        .replace(Regex("\\s+"), " ")
        .trim()

private fun footballDataTeamId(state: SweepstakeState, apiName: String): String? {
    val apiNorm = normaliseFootballDataName(apiName)
    return state.teams.firstOrNull { team ->
        normaliseFootballDataName(team.name) == apiNorm ||
            normaliseFootballDataName(displayTeamName(team.name)) == apiNorm ||
            team.id.equals(apiName, ignoreCase = true)
    }?.id
}

private fun footballDataRoundNumber(stage: String?): Int {
    val clean = stage.orEmpty().uppercase()
    return when {
        "GROUP" in clean -> 0
        "LAST_32" in clean || "ROUND_OF_32" in clean -> 32
        "LAST_16" in clean || "ROUND_OF_16" in clean -> 16
        "QUARTER" in clean -> 8
        "SEMI" in clean -> 4
        "THIRD" in clean -> 3
        "FINAL" in clean -> 2
        else -> 0
    }
}

private fun footballDataStageName(stage: String?): String {
    val clean = stage.orEmpty().uppercase()
    return when {
        "GROUP" in clean -> "group"
        "LAST_32" in clean || "ROUND_OF_32" in clean -> "Round of 32"
        "LAST_16" in clean || "ROUND_OF_16" in clean -> "Round of 16"
        "QUARTER" in clean -> "Quarter-finals"
        "SEMI" in clean -> "Semi-finals"
        "THIRD" in clean -> "Third Place Playoff"
        "FINAL" in clean -> "Final"
        else -> stage.orEmpty().replace("_", " ").lowercase().replaceFirstChar { it.titlecase() }
    }
}

private fun footballDataGroupName(raw: String?): String {
    val clean = raw.orEmpty()
        .removePrefix("GROUP_")
        .removePrefix("Group ")
        .trim()
    return if (clean.length == 1) clean else clean.takeLast(1)
}

private fun splitFootballDataDateTime(utcDate: String?): Pair<String, String> {
    if (utcDate.isNullOrBlank()) return "" to ""

    return try {
        val zoned = Instant.parse(utcDate).atZone(ZoneId.systemDefault())
        val date = zoned.format(DateTimeFormatter.ofPattern("yyyy-MM-dd"))
        val time = zoned.format(DateTimeFormatter.ofPattern("HH:mm"))
        date to time
    } catch (_: Exception) {
        val parts = utcDate.replace("Z", "").split("T")
        parts.getOrNull(0).orEmpty() to parts.getOrNull(1)?.take(5).orEmpty()
    }
}

private fun findMatchByTeams(matches: List<Match>, homeId: String, awayId: String): Match? =
    matches.firstOrNull { it.homeId == homeId && it.awayId == awayId }
        ?: matches.firstOrNull { it.homeId == awayId && it.awayId == homeId }

private fun readFootballDataScore(score: JSONObject?): Pair<Int?, Int?> {
    if (score == null) return null to null

    fun pairFrom(key: String): Pair<Int?, Int?> {
        val section = score.optJSONObject(key) ?: return null to null
        val home = if (section.isNull("home")) null else section.optInt("home")
        val away = if (section.isNull("away")) null else section.optInt("away")
        return home to away
    }

    val fullTime = pairFrom("fullTime")
    if (fullTime.first != null && fullTime.second != null) return fullTime

    val regularTime = pairFrom("regularTime")
    if (regularTime.first != null && regularTime.second != null) return regularTime

    val extraTime = pairFrom("extraTime")
    if (extraTime.first != null && extraTime.second != null) return extraTime

    val penalties = pairFrom("penalties")
    if (penalties.first != null && penalties.second != null) return penalties

    val halfTime = pairFrom("halfTime")
    if (halfTime.first != null && halfTime.second != null) return halfTime

    return null to null
}

private fun isFootballDataScoredStatus(status: String): Boolean =
    status == "FINISHED" ||
        status == "IN_PLAY" ||
        status == "PAUSED" ||
        status == "AWARDED"

private fun footballDataKnockoutStageName(stage: String?): String {
    val clean = stage.orEmpty().uppercase().trim()
    return when (clean) {
        "LAST_32", "ROUND_OF_32" -> "Last 32"
        "LAST_16", "ROUND_OF_16" -> "Last 16"
        "QUARTER_FINALS", "QUARTER_FINAL", "QUARTER" -> "Quarter-finals"
        "SEMI_FINALS", "SEMI_FINAL", "SEMI" -> "Semi-finals"
        "THIRD_PLACE", "THIRD_PLACE_PLAYOFF", "THIRD_PLACE_GAME" -> "Third Place Playoff"
        "FINAL" -> "Final"
        "GROUP_STAGE", "GROUP" -> "Group"
        else -> clean
            .lowercase()
            .split("_")
            .filter { it.isNotBlank() }
            .joinToString(" ") { it.replaceFirstChar { ch -> ch.titlecase() } }
    }
}

private fun isFootballDataGroupStage(stage: String?): Boolean =
    stage.orEmpty().uppercase().trim() in setOf("GROUP_STAGE", "GROUP")

private fun findKnockoutMatchByTeams(matches: List<KnockoutMatch>, homeId: String, awayId: String): KnockoutMatch? =
    matches.firstOrNull { it.homeId == homeId && it.awayId == awayId }
        ?: matches.firstOrNull { it.homeId == awayId && it.awayId == homeId }

private fun footballDataKnockoutMatchId(apiMatch: JSONObject, stage: String, index: Int): String =
    apiMatch.optInt("id", 0).takeIf { it != 0 }?.toString()
        ?: "fd-ko-${stage.lowercase().replace(Regex("[^a-z0-9]+"), "-")}-$index"

private fun fetchFootballData(state: SweepstakeState): SweepstakeState {
    val connection = (URL(FOOTBALL_DATA_MATCHES_URL).openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 15000
        readTimeout = 15000
        setRequestProperty("X-Auth-Token", FOOTBALL_DATA_API_KEY)
        setRequestProperty("Accept", "application/json")
    }

    try {
        val responseCode = connection.responseCode
        val responseBody = if (responseCode in 200..299) {
            connection.inputStream.bufferedReader().use { it.readText() }
        } else {
            val errorBody = connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
            throw IllegalStateException("Football-Data.org returned HTTP $responseCode ${errorBody.take(160)}")
        }

        val root = JSONObject(responseBody)
        val apiMatches = root.optJSONArray("matches") ?: JSONArray()
        val updatedMatches = state.matches.toMutableList()
        val updatedKnockoutMatches = state.knockoutMatches.toMutableList()

        for (i in 0 until apiMatches.length()) {
            val apiMatch = apiMatches.optJSONObject(i) ?: continue

            val homeName = apiMatch.optJSONObject("homeTeam")?.optString("name").orEmpty()
            val awayName = apiMatch.optJSONObject("awayTeam")?.optString("name").orEmpty()

            val status = apiMatch.optString("status")
            val stageRaw = apiMatch.optString("stage")
            val group = footballDataGroupName(apiMatch.optString("group"))
            val round = footballDataRoundNumber(stageRaw)
            val stage = footballDataStageName(stageRaw)
            val utcDate = apiMatch.optString("utcDate")
            val (date, time) = splitFootballDataDateTime(utcDate)

            val scoreObject = apiMatch.optJSONObject("score")
            val (homeScore, awayScore) = readFootballDataScore(scoreObject)
            val hasScore = homeScore != null && awayScore != null
            val complete = (status == "FINISHED" || status == "AWARDED") && hasScore

            val homeId = footballDataTeamId(state, homeName).orEmpty()
            val awayId = footballDataTeamId(state, awayName).orEmpty()

            if (!isFootballDataGroupStage(stageRaw)) {
                val knockoutStage = footballDataKnockoutStageName(stageRaw)
                val sourceKey = apiMatch.optInt("id", 0).takeIf { it != 0 }?.toString().orEmpty()
                val existingKnockout = updatedKnockoutMatches.firstOrNull {
                    sourceKey.isNotBlank() && it.sourceKey == sourceKey
                } ?: if (homeId.isNotBlank() && awayId.isNotBlank()) {
                    findKnockoutMatchByTeams(updatedKnockoutMatches, homeId, awayId)
                } else {
                    null
                }
                val existingKnockoutIndex = existingKnockout?.let { updatedKnockoutMatches.indexOf(it) } ?: -1

                val nextKnockout = if (existingKnockout != null) {
                    val sameOrientation = homeId.isBlank() || awayId.isBlank() || (existingKnockout.homeId == homeId && existingKnockout.awayId == awayId)
                    val mappedHomeScore = if (sameOrientation) homeScore else awayScore
                    val mappedAwayScore = if (sameOrientation) awayScore else homeScore

                    existingKnockout.copy(
                        stage = knockoutStage,
                        homeId = existingKnockout.homeId.ifBlank { homeId },
                        awayId = existingKnockout.awayId.ifBlank { awayId },
                        homeName = displayTeamName(homeName).ifBlank { existingKnockout.homeName },
                        awayName = displayTeamName(awayName).ifBlank { existingKnockout.awayName },
                        homeScore = if (hasScore && isFootballDataScoredStatus(status)) mappedHomeScore else existingKnockout.homeScore,
                        awayScore = if (hasScore && isFootballDataScoredStatus(status)) mappedAwayScore else existingKnockout.awayScore,
                        complete = complete || existingKnockout.complete,
                        date = if (date.isNotBlank()) date else existingKnockout.date,
                        time = if (time.isNotBlank()) time else existingKnockout.time,
                        ground = apiMatch.optString("venue").ifBlank { existingKnockout.ground },
                        sourceKey = apiMatch.optInt("id", 0).takeIf { it != 0 }?.toString() ?: existingKnockout.sourceKey
                    )
                } else {
                    KnockoutMatch(
                        id = footballDataKnockoutMatchId(apiMatch, knockoutStage, i),
                        stage = knockoutStage,
                        homeId = homeId,
                        awayId = awayId,
                        homeName = displayTeamName(homeName),
                        awayName = displayTeamName(awayName),
                        homeScore = if (hasScore && isFootballDataScoredStatus(status)) homeScore else null,
                        awayScore = if (hasScore && isFootballDataScoredStatus(status)) awayScore else null,
                        winnerId = "",
                        complete = complete,
                        date = date,
                        time = time,
                        ground = apiMatch.optString("venue"),
                        sourceKey = apiMatch.optInt("id", 0).takeIf { it != 0 }?.toString().orEmpty()
                    )
                }

                if (existingKnockoutIndex >= 0) {
                    updatedKnockoutMatches[existingKnockoutIndex] = nextKnockout
                } else {
                    updatedKnockoutMatches.add(nextKnockout)
                }

                continue
            }

            if (homeId.isBlank() || awayId.isBlank()) continue

            val existing = findMatchByTeams(updatedMatches, homeId, awayId)
            val existingIndex = existing?.let { updatedMatches.indexOf(it) } ?: -1

            val next = if (existing != null) {
                existing.copy(
                    stage = if (stage.isNotBlank()) stage else existing.stage,
                    group = if (group.isNotBlank()) group else existing.group,
                    round = if (round != 0) round else existing.round,
                    homeId = homeId,
                    awayId = awayId,
                    homeScore = if (hasScore) homeScore else existing.homeScore,
                    awayScore = if (hasScore) awayScore else existing.awayScore,
                    complete = complete || existing.complete,
                    date = if (date.isNotBlank()) date else existing.date,
                    time = if (time.isNotBlank()) time else existing.time
                )
            } else {
                Match(
                    id = apiMatch.optInt("id", updatedMatches.size + 1).toString(),
                    stage = stage,
                    group = group,
                    round = round,
                    homeId = homeId,
                    awayId = awayId,
                    homeSlot = 0,
                    awaySlot = 0,
                    homeScore = if (hasScore && isFootballDataScoredStatus(status)) homeScore else null,
                    awayScore = if (hasScore && isFootballDataScoredStatus(status)) awayScore else null,
                    complete = complete,
                    date = date,
                    time = time,
                    ground = apiMatch.optString("venue")
                )
            }

            if (existingIndex >= 0) {
                updatedMatches[existingIndex] = next
            } else {
                updatedMatches.add(next)
            }
        }

        return state.copy(matches = updatedMatches, knockoutMatches = updatedKnockoutMatches, matchSource = "Football-Data.org")
    } finally {
        connection.disconnect()
    }
}

private fun teamIdByName(state: SweepstakeState, name: String?): String { val key = norm(sourceNameToAppName(name)); return state.teams.firstOrNull { norm(it.name) == key || norm(sourceNameToAppName(it.name)) == key }?.id ?: "" }
private fun stageFromRound(round: String): String { val v = round.lowercase(); return when { "round of 32" in v || "last 32" in v -> "Last 32"; "round of 16" in v || "last 16" in v -> "Last 16"; "quarter" in v -> "Quarter-finals"; "semi" in v -> "Semi-finals"; "third" in v -> ""; "final" in v -> "Final"; else -> "" } }
private fun scoreFrom(o: JSONObject): Pair<Int, Int>? { val ft = o.optJSONObject("score")?.optJSONArray("ft") ?: return null; if (ft.length() < 2) return null; return ft.optInt(0) to ft.optInt(1) }
private fun dateFrom(o: JSONObject): String {
    val raw = listOf("utcDate", "datetime", "kickoff", "scheduled", "date")
        .firstNotNullOfOrNull { key -> o.optString(key).takeIf { it.isNotBlank() } }
        ?: return ""
    return try {
        Instant.parse(raw).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("yyyy-MM-dd"))
    } catch (_: Exception) {
        raw.take(10)
    }
}
private fun timeFrom(o: JSONObject): String {
    val raw = listOf("utcDate", "datetime", "kickoff", "scheduled")
        .firstNotNullOfOrNull { key -> o.optString(key).takeIf { it.isNotBlank() } }
        ?: o.optString("time")
    return try {
        Instant.parse(raw).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("HH:mm"))
    } catch (_: Exception) {
        raw.substringAfter("T", raw).replace("Z", "").take(5)
    }
}
private fun groundFrom(o: JSONObject): String { val v = o.opt("ground") ?: o.opt("stadium") ?: o.opt("venue") ?: o.opt("location") ?: o.opt("city") ?: return ""; return if (v is JSONObject) listOf(v.optString("name"), v.optString("city")).firstOrNull { it.isNotBlank() } ?: "" else v.toString() }
private fun httpGet(url: String): String { val c = URL(url).openConnection() as HttpURLConnection; c.connectTimeout = 15000; c.readTimeout = 15000; c.setRequestProperty("Accept", "application/json"); if (c.responseCode !in 200..299) error("HTTP ${c.responseCode}"); return c.inputStream.bufferedReader().use { it.readText() } }
private fun <T> runAsync(context: Context, block: () -> T, ok: (T) -> Unit, fail: (Throwable) -> Unit) { Thread { try { val r = block(); Handler(Looper.getMainLooper()).post { ok(r) } } catch (t: Throwable) { Handler(Looper.getMainLooper()).post { fail(t) } } }.start() }

private fun parseCsvLine(line: String): List<String> { val out = mutableListOf<String>(); var cur = ""; var quoted = false; line.forEachIndexed { i, ch -> when { ch == '"' && quoted && i + 1 < line.length && line[i + 1] == '"' -> cur += '"'; ch == '"' -> quoted = !quoted; ch == ',' && !quoted -> { out += cur.trim(); cur = "" }; else -> cur += ch } }; out += cur.trim(); return out }
private fun applyMappingsCsv(state: SweepstakeState, text: String): SweepstakeState { val lines = text.lines().filter { it.isNotBlank() }; if (lines.isEmpty()) return state; val headers = parseCsvLine(lines.first()).map { norm(it) }; val pi = headers.indexOfFirst { it == "participant" || it == "name" }; val ti = headers.indexOfFirst { it == "team" || it == "country" }; if (pi < 0 || ti < 0) return state; var participants = state.participants; var assignments = state.assignments; lines.drop(1).forEach { line -> val c = parseCsvLine(line); val pname = c.getOrNull(pi)?.trim().orEmpty(); val tname = c.getOrNull(ti)?.trim().orEmpty(); if (pname.isBlank() || tname.isBlank()) return@forEach; val p = participants.firstOrNull { norm(it.name) == norm(pname) } ?: Participant(name = pname).also { participants += it }; val tid = teamIdByName(state, tname); if (tid.isNotBlank()) assignments = assignments.filterNot { it.participantId == p.id || it.teamId == tid } + Assignment(participantId = p.id, teamId = tid) }; return state.copy(participants = participants, assignments = assignments) }
private fun applyOddsCsv(state: SweepstakeState, text: String, source: String): SweepstakeState { val lines = text.lines().filter { it.isNotBlank() }; if (lines.isEmpty()) return state; val headers = parseCsvLine(lines.first()).map { norm(it) }; val ti = headers.indexOfFirst { it == "team" || it == "country" || it == "name" }.coerceAtLeast(0); val oi = headers.indexOfFirst { "odd" in it || "price" in it }.let { if (it < 0) 1 else it }; val map = state.odds.toMutableMap(); lines.drop(1).forEach { line -> val c = parseCsvLine(line); val teamName = c.getOrNull(ti).orEmpty(); val dec = valueToDecimal(c.getOrNull(oi)); if (teamName.isNotBlank() && dec != null) map[norm(displayTeamName(teamName))] = OddsEntry(displayTeamName(teamName), dec, decimalToFractional(dec), source) }; return state.copy(odds = map, oddsSource = source) }

private fun fetchTheOddsApiOdds(state: SweepstakeState, apiKey: String): SweepstakeState {
    val winnerOdds = fetchWinnerOdds(state, apiKey)
    val matchOdds = fetchMatchH2hOdds(apiKey)
    if (winnerOdds.isEmpty() && matchOdds.isEmpty()) error("No World Cup odds returned for the configured regions.")
    return state.copy(
        odds = state.odds + winnerOdds,
        matchOdds = state.matchOdds + matchOdds,
        oddsSource = "The Odds API · winner outrights + match h2h (draw included)"
    )
}

private fun fetchWinnerOdds(state: SweepstakeState, apiKey: String): Map<String, OddsEntry> {
    val url = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup_winner/odds/" +
        "?apiKey=${java.net.URLEncoder.encode(apiKey, "UTF-8")}" +
        "&regions=uk,eu,us,au&markets=outrights&oddsFormat=decimal&dateFormat=iso"
    val events = JSONArray(httpGet(url))
    val best = linkedMapOf<String, OddsEntry>()
    for (i in 0 until events.length()) {
        val event = events.optJSONObject(i) ?: continue
        val bookmakers = event.optJSONArray("bookmakers") ?: continue
        for (b in 0 until bookmakers.length()) {
            val bookmaker = bookmakers.optJSONObject(b) ?: continue
            val bookmakerName = bookmaker.optString("title", bookmaker.optString("key", "The Odds API"))
            val markets = bookmaker.optJSONArray("markets") ?: continue
            for (m in 0 until markets.length()) {
                val market = markets.optJSONObject(m) ?: continue
                if (market.optString("key") != "outrights") continue
                val outcomes = market.optJSONArray("outcomes") ?: continue
                for (o in 0 until outcomes.length()) {
                    val outcome = outcomes.optJSONObject(o) ?: continue
                    val sourceTeam = displayTeamName(outcome.optString("name"))
                    val decimal = outcome.optDouble("price", 0.0)
                    if (sourceTeam.isBlank() || decimal <= 1.0) continue
                    val appTeam = state.teams.firstOrNull { norm(it.name) == norm(sourceTeam) || norm(sourceNameToAppName(it.name)) == norm(sourceTeam) }?.name ?: sourceTeam
                    val key = norm(appTeam)
                    val current = best[key]
                    if (current == null || decimal > current.decimal) {
                        best[key] = OddsEntry(appTeam, decimal, decimalToFractional(decimal), "The Odds API · $bookmakerName")
                    }
                }
            }
        }
    }
    return best
}

private fun fetchMatchH2hOdds(apiKey: String): Map<String, MatchOddsEntry> {
    // h2h is The Odds API match-result market. For soccer, it includes Home, Draw and Away outcomes.
    // One bookmaker is used per match so the displayed Home/Draw/Away odds all share the same source.
    val url = "https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/" +
        "?apiKey=${java.net.URLEncoder.encode(apiKey, "UTF-8")}" +
        "&regions=uk,eu,us,au&markets=h2h&oddsFormat=decimal&dateFormat=iso"
    val events = runCatching { JSONArray(httpGet(url)) }.getOrElse { JSONArray() }
    val matchOdds = linkedMapOf<String, MatchOddsEntry>()
    for (i in 0 until events.length()) {
        val event = events.optJSONObject(i) ?: continue
        val home = displayTeamName(event.optString("home_team"))
        val away = displayTeamName(event.optString("away_team"))
        if (home.isBlank() || away.isBlank()) continue
        val bookmakers = event.optJSONArray("bookmakers") ?: continue
        var chosen: MatchOddsEntry? = null
        for (b in 0 until bookmakers.length()) {
            val bookmaker = bookmakers.optJSONObject(b) ?: continue
            val bookmakerName = bookmaker.optString("title", bookmaker.optString("key", "The Odds API"))
            val markets = bookmaker.optJSONArray("markets") ?: continue
            for (m in 0 until markets.length()) {
                val market = markets.optJSONObject(m) ?: continue
                if (market.optString("key") != "h2h") continue
                val outcomes = market.optJSONArray("outcomes") ?: continue
                var homeDecimal: Double? = null
                var drawDecimal: Double? = null
                var awayDecimal: Double? = null
                for (o in 0 until outcomes.length()) {
                    val outcome = outcomes.optJSONObject(o) ?: continue
                    val name = displayTeamName(outcome.optString("name"))
                    val decimal = outcome.optDouble("price", 0.0).takeIf { it > 1.0 } ?: continue
                    when {
                        norm(name) == norm(home) -> homeDecimal = decimal
                        norm(name) == "draw" -> drawDecimal = decimal
                        norm(name) == norm(away) -> awayDecimal = decimal
                    }
                }
                if (homeDecimal != null || drawDecimal != null || awayDecimal != null) {
                    chosen = MatchOddsEntry(
                        homeDecimal = homeDecimal,
                        drawDecimal = drawDecimal,
                        awayDecimal = awayDecimal,
                        source = bookmakerName
                    )
                    break
                }
            }
            if (chosen != null) break
        }
        chosen?.let { matchOdds[matchOddsKey(home, away)] = it }
    }
    return matchOdds
}

private fun valueToDecimal(raw: Any?): Double? { if (raw == null) return null; if (raw is Number) return raw.toDouble().takeIf { it > 1 }; val text = raw.toString().trim(); Regex("^(\\d+)\\s*/\\s*(\\d+)$").find(text)?.let { val a = it.groupValues[1].toDouble(); val b = it.groupValues[2].toDouble(); if (b > 0) return 1 + a / b }; return Regex("\\d+(?:\\.\\d+)?").find(text)?.value?.toDoubleOrNull()?.takeIf { it > 1 } }
private fun decimalToFractional(decimal: Double): String { if (decimal <= 1) return ""; val value = decimal - 1; var bestN = 1; var bestD = 1; var bestErr = Double.MAX_VALUE; listOf(1,2,3,4,5,6,7,8,10,11,12,14,16,20,25,33,40,50,66,80,100,150,200,250,500).forEach { d -> val n = max(1, kotlin.math.round(value * d).toInt()); val err = abs(n.toDouble() / d - value); if (err < bestErr) { bestErr = err; bestN = n; bestD = d } }; return "$bestN/$bestD" }
private fun seedKnockoutsFromGroups(state: SweepstakeState): List<KnockoutMatch> { val qualifiers = GROUPS.flatMap { standingsForGroup(state, it).take(2) }; return qualifiers.chunked(2).mapIndexed { i, pair -> KnockoutMatch(stage = "Last 32", homeId = pair.getOrNull(0)?.teamId ?: "", awayId = pair.getOrNull(1)?.teamId ?: "", homeName = pair.getOrNull(0)?.team ?: "TBC", awayName = pair.getOrNull(1)?.team ?: "TBC", sourceKey = "seed-${i+1}") } }
private fun teamName(state: SweepstakeState, id: String) = state.teams.find { it.id == id }?.name?.ifBlank { "TBC" } ?: "TBC"
private fun Double.format(decimals: Int) = "% .${decimals}f".format(this).trim()
