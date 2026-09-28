#!/usr/bin/php
<?php

$lat = 54.989342;
$lon = 73.368212;

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, "https://yandex.ru/pogoda/omsk?lat=$lat&lon=$lon");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'GET');
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language: en-US,en;q=0.9,ru;q=0.8',
    'cache-control: max-age=0',
    'device-memory: 8',
    'dnt: 1',
    'downlink: 0.4',
    'dpr: 1',
    'ect: 3g',
    'priority: u=0, i',
    'rtt: 900',
    'sec-ch-ua: "Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    'sec-ch-ua-arch: "x86"',
    'sec-ch-ua-bitness: "64"',
    'sec-ch-ua-full-version: "128.0.6613.188"',
    'sec-ch-ua-full-version-list: "Chromium";v="128.0.6613.188", "Not;A=Brand";v="24.0.0.0", "Google Chrome";v="128.0.6613.188"',
    'sec-ch-ua-mobile: ?0',
    'sec-ch-ua-model: ""',
    'sec-ch-ua-platform: "Linux"',
    'sec-ch-ua-platform-version: "6.8.0"',
    'sec-ch-ua-wow64: ?0',
    'sec-fetch-dest: document',
    'sec-fetch-mode: navigate',
    'sec-fetch-site: none',
    'sec-fetch-user: ?1',
    'upgrade-insecure-requests: 1',
    'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'viewport-width: 1574'
]);
$html = curl_exec($ch);
curl_close($ch);

$doc = new DOMDocument('1.0', 'UTF-8');
$doc->loadhtml('<?xml encoding="UTF-8">' . $html, LIBXML_NOERROR);
//$xpath = new DOMXPath($doc);
//$node = $xpath->query('//div[@class="fact__hour-elem"]');

$divs = $doc->getElementsByTagName('div');
foreach ($divs as $div) {
    // Loop through the DIVs looking for one withan id of "content"
    // Then echo out its contents (pardon the pun)
    if ($div->getAttribute('class') === 'fact__hour-elem') {
        // icon_thumb_(.*)
        // ovc-ra-sn -- пасмурно, дождь со снегом
        // ovc -- пасмурно
        // bkn-n, bkn-d -- облачно с прояснениями
        // bkn-m-ra-n -- небольшой дождь
        // skc-d, skc-n -- ясно
        $skyprev = $m[1] ?? '';
        $img = $div->getElementsByTagName('img')->item(0);
        if (preg_match('/icon_thumb_([^\s]+)/', $img->attributes->getNamedItem("class")->value, $m)) {
            if ($m[1] == 'sunset') {
                $before = $skyprev;
                break;
            }
            if (!empty($argv[1])) echo $m[1] . " | ";
        }
        $ints = $div->getElementsByTagName('div');
        foreach ($ints as $int) {
            if ($int->getAttribute('class') === 'fact__hour-label') {
                if (!empty($argv[1])) echo $int->nodeValue . " | ";
            }
            if ($int->getAttribute('class') === 'fact__hour-temp') {
                if (!empty($argv[1])) echo $int->nodeValue . " | ";
            }
        }
        if (!empty($argv[1])) echo "\n";
    }
}
echo $before;
