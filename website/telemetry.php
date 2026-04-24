<?php
/**
 * Bristlenose telemetry endpoint (Level 0, alpha).
 *
 * Receives batched tag-rejection events from TestFlight alpha testers and
 * appends one row per event to data/telemetry.csv. No per-event email
 * (would be spammy at volume). Download the CSV with the same token-gated
 * GET pattern as feedback.php.
 *
 * Level 0 = four fields only: tag_id, prompt_version, event_type, researcher_id.
 * No timestamps, no study IDs, no quote content, no participant data.
 * See docs/methodology/tag-rejections-are-great.md for the spec.
 *
 * Setup:
 *   1. Upload this file to your web root (bristlenose.app/telemetry.php)
 *   2. Create a "data/" directory next to it: mkdir data
 *   3. Protect it from web access: echo "Deny from all" > data/.htaccess
 *      (shared with feedback.php — same data/ dir)
 *   4. Set DOWNLOAD_TOKEN below (reuse the feedback.php token or mint a new one)
 *
 * CSV download:
 *   GET telemetry.php?download=1&token=<DOWNLOAD_TOKEN>
 */

// ── Config ───────────────────────────────────────────────────────────────

$DOWNLOAD_TOKEN = 'CHANGE_ME_TO_A_RANDOM_STRING'; // bin2hex(random_bytes(20))

$MAX_EVENTS_PER_BATCH = 500;
$MAX_BODY_BYTES       = 131072; // 128 KB, ~1000 maxed-out events

// ── Paths ────────────────────────────────────────────────────────────────

$DATA_DIR = __DIR__ . '/data';
$CSV_FILE = $DATA_DIR . '/telemetry.csv';

// ── Guardrail: refuse to run if the placeholder token wasn't rotated ─────
//
// If /deploy-website rsyncs this file without an edit, the download endpoint
// would ship with a publicly-known token. Fail every request loudly until
// the operator replaces the placeholder.

if ($DOWNLOAD_TOKEN === 'CHANGE_ME_TO_A_RANDOM_STRING') {
    http_response_code(503);
    header('Content-Type: text/plain');
    echo "Endpoint not configured: rotate \$DOWNLOAD_TOKEN in telemetry.php before deploying.\n";
    exit;
}

// ── CORS (Mac app, dev reports, future web contexts) ─────────────────────

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// ── CSV download ─────────────────────────────────────────────────────────

if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['download'])) {
    if (!isset($_GET['token']) || !hash_equals($DOWNLOAD_TOKEN, $_GET['token'])) {
        http_response_code(403);
        echo 'Forbidden';
        exit;
    }
    if (!file_exists($CSV_FILE)) {
        http_response_code(404);
        echo 'No telemetry yet';
        exit;
    }
    header('Content-Type: text/csv');
    header('Content-Disposition: attachment; filename="bristlenose-telemetry.csv"');
    readfile($CSV_FILE);
    exit;
}

// ── Receive batched events ───────────────────────────────────────────────

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo 'Method not allowed';
    exit;
}

$body = file_get_contents('php://input');
if (strlen($body) > $MAX_BODY_BYTES) {
    http_response_code(413);
    echo 'Payload too large';
    exit;
}
$data = json_decode($body, true);

if (!$data || !isset($data['events']) || !is_array($data['events']) || empty($data['events'])) {
    http_response_code(400);
    echo 'Bad request: expected {"events": [...]} with at least one event';
    exit;
}

if (count($data['events']) > $MAX_EVENTS_PER_BATCH) {
    http_response_code(400);
    echo "Bad request: batch too large (max $MAX_EVENTS_PER_BATCH events)";
    exit;
}

$VALID_EVENT_TYPES = ['suggested', 'accepted', 'rejected', 'edited'];
$EXPECTED_FIELDS   = ['tag_id', 'prompt_version', 'event_type', 'researcher_id'];

/**
 * Strip control characters and neutralise leading CSV-formula markers.
 *
 * fputcsv() already quotes fields containing commas, quotes, and newlines,
 * but it does NOT prefix =/+/-/@ with a tick — opening the CSV in Excel
 * would evaluate a cell beginning with `=HYPERLINK("http://evil")`. Strip
 * newline / carriage return / null first so a single forged field can't
 * forge additional rows in downstream tools, then prefix formula-starters
 * with a single quote.
 */
function bn_csv_safe(string $s): string {
    $s = str_replace(["\r", "\n", "\0"], '', $s);
    if ($s !== '' && in_array($s[0], ['=', '+', '-', '@', "\t"], true)) {
        $s = "'" . $s;
    }
    return $s;
}

$rows = [];
foreach ($data['events'] as $ev) {
    if (!is_array($ev)) {
        http_response_code(400);
        echo 'Bad request: each event must be an object';
        exit;
    }

    // Reject unknown fields — enforces the methodology doc's
    // "Four fields per event. Nothing else." invariant.
    foreach (array_keys($ev) as $key) {
        if (!in_array($key, $EXPECTED_FIELDS, true)) {
            http_response_code(400);
            echo "Bad request: unexpected field: $key";
            exit;
        }
    }

    $tag_id         = isset($ev['tag_id'])         ? (string) $ev['tag_id']         : '';
    $prompt_version = isset($ev['prompt_version']) ? (string) $ev['prompt_version'] : '';
    $event_type     = isset($ev['event_type'])     ? (string) $ev['event_type']     : '';
    $researcher_id  = isset($ev['researcher_id'])  ? (string) $ev['researcher_id']  : '';

    if ($tag_id === '' || $prompt_version === '' || $event_type === '' || $researcher_id === '') {
        http_response_code(400);
        echo 'Bad request: missing required field (tag_id, prompt_version, event_type, researcher_id)';
        exit;
    }
    if (!in_array($event_type, $VALID_EVENT_TYPES, true)) {
        http_response_code(400);
        echo 'Bad request: event_type must be one of: ' . implode(', ', $VALID_EVENT_TYPES);
        exit;
    }

    // Input caps — defence in depth against overlong or malformed input.
    // Sanitise before write: strip control chars, neutralise formula chars.
    $rows[] = [
        bn_csv_safe(substr($tag_id,         0, 100)),
        bn_csv_safe(substr($prompt_version, 0, 80)),
        $event_type, // enum-validated above; no sanitiser needed
        bn_csv_safe(substr($researcher_id,  0, 64)),
    ];
}

// ── Append to CSV ────────────────────────────────────────────────────────

if (!is_dir($DATA_DIR)) {
    mkdir($DATA_DIR, 0750, true);
}

$needs_header = !file_exists($CSV_FILE);
$fp = fopen($CSV_FILE, 'a');
if ($fp) {
    if ($needs_header) {
        fputcsv($fp, ['tag_id', 'prompt_version', 'event_type', 'researcher_id']);
    }
    foreach ($rows as $row) {
        fputcsv($fp, $row);
    }
    fclose($fp);
}

// ── Response ─────────────────────────────────────────────────────────────

http_response_code(200);
header('Content-Type: application/json');
echo json_encode(['ok' => true, 'received' => count($rows)]);
