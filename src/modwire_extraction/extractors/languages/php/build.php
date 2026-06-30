#!/usr/bin/env php
<?php

declare(strict_types=1);

$root = __DIR__;
$output = $root . '/script.php';
$pharPath = $root . '/script.phar';

if (file_exists($output)) {
    unlink($output);
}
if (file_exists($pharPath)) {
    unlink($pharPath);
}

$phar = new Phar($pharPath);
$phar->startBuffering();
$phar->setSignatureAlgorithm(Phar::SHA256);
$phar->addFile($root . '/script.src.php', 'script.src.php');

$vendorRoot = $root . '/vendor';
if (!is_dir($vendorRoot)) {
    fwrite(STDERR, "Composer vendor directory is missing. Run composer install first.\n");
    exit(1);
}

$iterator = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator($vendorRoot, FilesystemIterator::SKIP_DOTS)
);

foreach ($iterator as $file) {
    if (!$file->isFile()) {
        continue;
    }
    $path = $file->getPathname();
    $relativePath = str_replace($root . '/', '', $path);
    $phar->addFile($path, $relativePath);
}

$phar->setStub(<<<'PHP'
#!/usr/bin/env php
<?php
Phar::mapPhar('script.php');
require 'phar://script.php/script.src.php';
__HALT_COMPILER();
PHP);
$phar->stopBuffering();
rename($pharPath, $output);
chmod($output, 0755);
