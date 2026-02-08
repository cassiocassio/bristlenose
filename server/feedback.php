<?php
/**
 * Bristlenose feedback endpoint.
 *
 * Receives JSON POST { version, rating, message }, appends to a CSV file,
 * and emails a notification. Deploy to Dreamhost (or any PHP host).
 *
 * Setup:
 *   1. Upload this file to your web root (e.g. cassiocassio.co.uk/feedback.php)
 *   2. Create a "data/" directory next to it: mkdir data
 *   3. Protect it from web access: echo "Deny from all" > data/.htaccess
 *   4. Set the two config values below
 *   5. Set BRISTLENOSE_FEEDBACK_URL in render_html.py to the public URL
 *
 * CSV download:
 *   GET feedback.php?download=1&token=<DOWNLOAD_TOKEN>
 */

// ── Config ───────────────────────────────────────────────────────────────

$EMAIL_TO       = 'martin@cassiocassio.co.uk';   // change to your email
$DOWNLOAD_TOKEN = 'CHANGE_ME_TO_A_RANDOM_STRING'; // e.g. bin2hex(random_bytes(20))

// ── Paths ────────────────────────────────────────────────────────────────

$DATA_DIR = __DIR__ . '/data';
$CSV_FILE = $DATA_DIR . '/feedback.csv';

// ── CORS (reports are served from file:// or other origins) ──────────────

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// ── CSV download ─────────────────────────────────────────────────────────

if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['download'])) {
    if (!isset($_GET['token']) || $_GET['token'] !== $DOWNLOAD_TOKEN) {
        http_response_code(403);
        echo 'Forbidden';
        exit;
    }
    if (!file_exists($CSV_FILE)) {
        http_response_code(404);
        echo 'No feedback yet';
        exit;
    }
    header('Content-Type: text/csv');
    header('Content-Disposition: attachment; filename="bristlenose-feedback.csv"');
    readfile($CSV_FILE);
    exit;
}

// ── Receive feedback ─────────────────────────────────────────────────────

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo 'Method not allowed';
    exit;
}

$body = file_get_contents('php://input');
$data = json_decode($body, true);

if (!$data || empty($data['rating'])) {
    http_response_code(400);
    echo 'Bad request';
    exit;
}

$version = substr($data['version'] ?? 'unknown', 0, 20);
$rating  = substr($data['rating']  ?? '',        0, 20);
$message = substr($data['message'] ?? '',        0, 2000);
$time    = gmdate('Y-m-d H:i:s');
$ip      = $_SERVER['REMOTE_ADDR'] ?? '';

// ── Append to CSV ────────────────────────────────────────────────────────

if (!is_dir($DATA_DIR)) {
    mkdir($DATA_DIR, 0750, true);
}

$needs_header = !file_exists($CSV_FILE);
$fp = fopen($CSV_FILE, 'a');
if ($fp) {
    if ($needs_header) {
        fputcsv($fp, ['time', 'version', 'rating', 'message', 'ip']);
    }
    fputcsv($fp, [$time, $version, $rating, $message, $ip]);
    fclose($fp);
}

// ── Email notification ───────────────────────────────────────────────────

$subject = "Bristlenose feedback: $rating (v$version)";
$body    = "Rating:  $rating\n"
         . "Version: $version\n"
         . "Time:    $time UTC\n\n"
         . ($message ? "Message:\n$message\n" : "(no message)\n");

mail($EMAIL_TO, $subject, $body, "From: martin@cassiocassio.co.uk");

// ── Response ─────────────────────────────────────────────────────────────

http_response_code(200);
header('Content-Type: application/json');
echo json_encode(['ok' => true]);
