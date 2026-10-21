<?php
// Serviço de login HTTP mínimo para o servidor Canary local de testes.
// Implementa o mesmo formato JSON do loginservice.php oficial (chaves observadas
// no client.exe 15.33: session/sessionkey, playdata/worlds/characters...),
// lendo contas do banco local. Só para uso em 127.0.0.1.
//
// Uso: php -S 127.0.0.1:8080 -t tibia-acessibilidade/servidor-local

$DB = ['host' => '127.0.0.1', 'user' => 'root', 'pass' => '', 'name' => 'canary_teste', 'port' => 3306];
$WORLD = ['id' => 0, 'name' => 'Teste Local', 'ip' => '127.0.0.1', 'port' => 7172];
$VOCATIONS = [0 => 'None', 1 => 'Sorcerer', 2 => 'Druid', 3 => 'Paladin', 4 => 'Knight',
    5 => 'Master Sorcerer', 6 => 'Elder Druid', 7 => 'Royal Paladin', 8 => 'Elite Knight', 9 => 'Monk', 10 => 'Exalted Monk'];

header('Content-Type: application/json');

if (!in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1', '::1'], true)) {
    http_response_code(403);
    exit(json_encode(['errorCode' => 3, 'errorMessage' => 'Somente acesso local.']));
}

function fail($message, $code = 3) {
    exit(json_encode(['errorCode' => $code, 'errorMessage' => $message]));
}

$request = json_decode(file_get_contents('php://input'), true) ?: [];
$type = $request['type'] ?? '';

if ($type === 'cacheinfo') {
    exit(json_encode(['playersonline' => 0, 'twitchstreams' => 0, 'twitchviewer' => 0, 'gamingyoutubestreams' => 0, 'gamingyoutubeviewer' => 0]));
}
if ($type === 'eventschedule') {
    exit(json_encode(['eventlist' => [], 'lastupdatetimestamp' => time()]));
}
if ($type === 'boostedcreature') {
    exit(json_encode(['boostedcreature' => false]));
}
if ($type !== 'login') {
    fail('Tipo de requisição não suportado: ' . $type);
}

$email = $request['email'] ?? '';
$password = $request['password'] ?? '';

$db = new mysqli($DB['host'], $DB['user'], $DB['pass'], $DB['name'], $DB['port']);
if ($db->connect_errno) {
    fail('Banco indisponível.');
}

$stmt = $db->prepare('SELECT id, password, premdays FROM accounts WHERE email = ? OR name = ? LIMIT 1');
$stmt->bind_param('ss', $email, $email);
$stmt->execute();
$account = $stmt->get_result()->fetch_assoc();
if (!$account || !hash_equals($account['password'], sha1($password))) {
    fail('Email ou senha incorretos.');
}

$stmt = $db->prepare('SELECT name, level, sex, vocation, looktype, lookhead, lookbody, looklegs, lookfeet, lookaddons FROM players WHERE account_id = ? AND deletion = 0 ORDER BY name');
$stmt->bind_param('i', $account['id']);
$stmt->execute();
$characters = [];
foreach ($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $p) {
    $characters[] = [
        'worldid' => $WORLD['id'], 'name' => $p['name'], 'ismale' => intval($p['sex']) === 1,
        'tutorial' => false, 'level' => intval($p['level']),
        'vocation' => $VOCATIONS[intval($p['vocation'])] ?? 'None',
        'outfitid' => intval($p['looktype']), 'headcolor' => intval($p['lookhead']),
        'torsocolor' => intval($p['lookbody']), 'legscolor' => intval($p['looklegs']),
        'detailcolor' => intval($p['lookfeet']), 'addonsflags' => intval($p['lookaddons']),
        'ishidden' => false, 'istournamentparticipant' => false, 'ismaincharacter' => false,
        'dailyrewardstate' => 0, 'remainingdailytournamentplaytime' => 0,
    ];
}

$world = [
    'id' => $WORLD['id'], 'name' => $WORLD['name'],
    'externaladdress' => $WORLD['ip'], 'externalport' => $WORLD['port'],
    'externaladdressprotected' => $WORLD['ip'], 'externalportprotected' => $WORLD['port'],
    'externaladdressunprotected' => $WORLD['ip'], 'externalportunprotected' => $WORLD['port'],
    'previewstate' => 0, 'location' => 'BRA', 'anticheatprotection' => false,
    'pvptype' => 0, 'istournamentworld' => false, 'restrictedstore' => false,
    'currenttournamentphase' => 2,
];

echo json_encode([
    'session' => [
        // Canary com authType = "password" espera "email\nsenha" como chave de sessão
        'sessionkey' => $email . "\n" . $password,
        'lastlogintime' => 0, 'ispremium' => true, 'premiumuntil' => time() + 365 * 86400,
        'status' => 'active', 'returnernotification' => false, 'showrewardnews' => false,
        'isreturner' => false, 'fpstracking' => false, 'optiontracking' => false,
        'tournamentticketpurchasestate' => 0, 'emailcoderequest' => false,
    ],
    'playdata' => ['worlds' => [$world], 'characters' => $characters],
]);
