#!/usr/bin/env php
<?php

function line_count_for_content(string $content): int {
    return max(1, substr_count($content, "\n") + 1);
}

function code_line_count_for_content(string $content): int {
    $count = 0;
    foreach (explode("\n", $content) as $line) {
        $trimmed = trim($line);
        if ($trimmed !== '' && !str_starts_with($trimmed, '//') && !str_starts_with($trimmed, '#') && !str_starts_with($trimmed, '/*') && !str_starts_with($trimmed, '*')) {
            $count++;
        }
    }
    return $count;
}

function token_line_value($token, int $fallbackLine): int {
    return is_array($token) ? $token[2] : $fallbackLine;
}

function token_text($token): string {
    return is_array($token) ? $token[1] : $token;
}

function normalize_namespace_reference(string $value): string {
    return trim(str_replace('/', '\\', $value), " \\");
}

function normalize_import_path(string $value): string {
    return trim(str_replace('\\', '/', $value), '/ ');
}

function import_parent_path(string $value): string {
    $normalizedPath = normalize_import_path($value);
    $parts = explode('/', $normalizedPath);
    array_pop($parts);
    return implode('/', $parts);
}

function is_name_token($token): bool {
    if (!is_array($token)) {
        return false;
    }

    $tokenId = $token[0];
    $valid = [T_STRING];
    if (defined('T_NS_SEPARATOR')) {
        $valid[] = T_NS_SEPARATOR;
    }
    if (defined('T_NAME_QUALIFIED')) {
        $valid[] = T_NAME_QUALIFIED;
    }
    if (defined('T_NAME_FULLY_QUALIFIED')) {
        $valid[] = T_NAME_FULLY_QUALIFIED;
    }
    if (defined('T_NAME_RELATIVE')) {
        $valid[] = T_NAME_RELATIVE;
    }

    return in_array($tokenId, $valid, true);
}

function imported_symbol_name(string $path): string {
    $parts = explode('/', normalize_import_path($path));
    return end($parts) ?: '';
}

function use_import_entry(string $usePath, bool $isAliased, int $statementId, bool $usesJoinedImport): array {
    $normalizedUsePath = normalize_namespace_reference($usePath);
    $symbolName = imported_symbol_name($normalizedUsePath);
    return [
        'path' => $normalizedUsePath,
        'is_relative' => false,
        'normalized_path' => normalize_import_path($normalizedUsePath),
        'imported_name' => '',
        'is_aliased' => $isAliased,
        'crossing_type' => 'symbol',
        'file_barrier_crossed' => true,
        'statement_id' => $statementId,
        'join_key' => import_parent_path($normalizedUsePath),
        'uses_joined_import' => $usesJoinedImport,
        'imported_symbols' => [
            [
                'name' => $symbolName,
                'alias' => '',
                'is_aliased' => $isAliased,
                'is_default' => false,
                'is_namespace' => false,
                'is_star' => false,
            ],
        ],
    ];
}

function use_statement_imports(array $tokens, int $useIndex, int $statementId): array {
    $count = count($tokens);
    $j = $useIndex + 1;
    $prefix = '';
    $imports = [];

    while ($j < $count && token_text($tokens[$j]) !== ';') {
        $token = $tokens[$j];
        if ($token === '{') {
            $j++;
            $name = '';
            $isAliased = false;
            while ($j < $count && token_text($tokens[$j]) !== '}') {
                $current = $tokens[$j];
                if ($current === ',') {
                    if ($name !== '') {
                        $imports[] = use_import_entry(
                            rtrim($prefix, '\\') . '\\' . $name,
                            $isAliased,
                            $statementId,
                            true
                        );
                    }
                    $name = '';
                    $isAliased = false;
                } elseif (is_array($current) && $current[0] === T_AS) {
                    $isAliased = true;
                    while ($j < $count && token_text($tokens[$j]) !== ',' && token_text($tokens[$j]) !== '}') {
                        $j++;
                    }
                    $j--;
                } elseif (is_name_token($current)) {
                    $name .= token_text($current);
                }
                $j++;
            }
            if ($name !== '') {
                $imports[] = use_import_entry(rtrim($prefix, '\\') . '\\' . $name, $isAliased, $statementId, true);
            }
            return $imports;
        }
        if ($token === ',') {
            if ($prefix !== '') {
                $imports[] = use_import_entry($prefix, false, $statementId, false);
            }
            $prefix = '';
        } elseif (is_array($token) && $token[0] === T_AS) {
            if ($prefix !== '') {
                $imports[] = use_import_entry($prefix, true, $statementId, false);
            }
            while ($j < $count && token_text($tokens[$j]) !== ',' && token_text($tokens[$j]) !== ';') {
                $j++;
            }
            $prefix = '';
            continue;
        } elseif (is_name_token($token)) {
            $prefix .= token_text($token);
        }
        $j++;
    }

    if ($prefix !== '') {
        $imports[] = use_import_entry($prefix, false, $statementId, false);
    }

    return $imports;
}

function member_visibility(array $tokens, int $functionIndex): string {
    for ($index = $functionIndex - 1; $index >= 0; $index--) {
        $token = $tokens[$index];
        if (!is_array($token)) {
            $text = token_text($token);
            if ($text === ';' || $text === '{' || $text === '}') {
                break;
            }
            continue;
        }

        $tokenId = $token[0];
        if (in_array($tokenId, [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT, T_STATIC, T_FINAL, T_ABSTRACT], true)) {
            continue;
        }
        if ($tokenId === T_PRIVATE) {
            return 'private';
        }
        if ($tokenId === T_PROTECTED) {
            return 'protected';
        }
        if ($tokenId === T_PUBLIC) {
            return 'public';
        }
        break;
    }

    return 'public';
}

function visibility_intent(string $name, string $visibility): string {
    $magicMethods = [
        '__call',
        '__callStatic',
        '__clone',
        '__construct',
        '__debugInfo',
        '__destruct',
        '__get',
        '__invoke',
        '__isset',
        '__serialize',
        '__set',
        '__set_state',
        '__sleep',
        '__toString',
        '__unserialize',
        '__unset',
        '__wakeup',
    ];
    if (in_array($name, $magicMethods, true)) {
        return $visibility;
    }
    if (str_starts_with($name, '__')) {
        return 'private';
    }
    if (str_starts_with($name, '_')) {
        return 'protected';
    }
    return $visibility;
}

function find_block_end_line(array $tokens, int $startIndex, int $fallbackLine): int {
    $depth = 0;
    $seenBrace = false;
    $currentLine = $fallbackLine;
    $count = count($tokens);

    for ($index = $startIndex; $index < $count; $index++) {
        $token = $tokens[$index];
        $currentLine = token_line_value($token, $currentLine);
        $text = token_text($token);

        if ($text === '{') {
            $depth++;
            $seenBrace = true;
            continue;
        }
        if ($text === '}') {
            if ($seenBrace) {
                $depth--;
                if ($depth === 0) {
                    return $currentLine;
                }
            }
            continue;
        }
        if (!$seenBrace && $text === ';') {
            return $currentLine;
        }
    }

    return $currentLine;
}

function find_parameter_bounds(array $tokens, int $functionIndex): array {
    $count = count($tokens);
    $openIndex = null;

    for ($index = $functionIndex; $index < $count; $index++) {
        $text = token_text($tokens[$index]);
        if ($text === '(') {
            $openIndex = $index;
            break;
        }
        if ($text === ';' || $text === '{') {
            return [null, null];
        }
    }

    if ($openIndex === null) {
        return [null, null];
    }

    $depth = 0;
    for ($index = $openIndex; $index < $count; $index++) {
        $text = token_text($tokens[$index]);
        if ($text === '(') {
            $depth++;
            continue;
        }
        if ($text === ')') {
            $depth--;
            if ($depth === 0) {
                return [$openIndex, $index];
            }
        }
    }

    return [$openIndex, null];
}

function parameter_counts(array $tokens, ?int $openIndex, ?int $closeIndex): array {
    if ($openIndex === null || $closeIndex === null || $closeIndex <= $openIndex + 1) {
        return ['declared_args' => 0, 'optional_args' => 0];
    }

    $declaredArgs = 0;
    $optionalArgs = 0;
    $segmentHasVariable = false;
    $segmentIsOptional = false;
    $depth = 0;

    $flushSegment = function () use (&$declaredArgs, &$optionalArgs, &$segmentHasVariable, &$segmentIsOptional): void {
        if ($segmentHasVariable) {
            $declaredArgs++;
            if ($segmentIsOptional) {
                $optionalArgs++;
            }
        }
        $segmentHasVariable = false;
        $segmentIsOptional = false;
    };

    for ($index = $openIndex + 1; $index < $closeIndex; $index++) {
        $token = $tokens[$index];
        $text = token_text($token);

        if ($text === '(' || $text === '[' || $text === '{') {
            $depth++;
            continue;
        }
        if ($text === ')' || $text === ']' || $text === '}') {
            $depth = max(0, $depth - 1);
            continue;
        }
        if ($text === ',' && $depth === 0) {
            $flushSegment();
            continue;
        }
        if (is_array($token) && $token[0] === T_VARIABLE) {
            $segmentHasVariable = true;
            continue;
        }
        if ($text === '=' && $depth === 0) {
            $segmentIsOptional = true;
            continue;
        }
        if ($text === '...') {
            $segmentIsOptional = true;
        }
    }

    $flushSegment();

    return ['declared_args' => $declaredArgs, 'optional_args' => $optionalArgs];
}

function is_visibility_token($token): bool {
    return is_array($token) && in_array($token[0], [T_PUBLIC, T_PROTECTED, T_PRIVATE], true);
}

function add_class_property(array &$classDefinition, string $name, bool $isOptional): void {
    foreach ($classDefinition['properties'] as &$property) {
        if ($property['name'] === $name) {
            $property['is_optional'] = $property['is_optional'] || $isOptional;
            return;
        }
    }
    unset($property);

    $classDefinition['properties'][] = [
        'name' => $name,
        'is_optional' => $isOptional,
    ];
}

function split_top_level_segments(array $tokens, int $startIndex, int $endIndex): array {
    $segments = [];
    $segmentStart = $startIndex;
    $depth = 0;
    for ($index = $startIndex; $index < $endIndex; $index++) {
        $text = token_text($tokens[$index]);
        if ($text === '(' || $text === '[' || $text === '{') {
            $depth++;
            continue;
        }
        if ($text === ')' || $text === ']' || $text === '}') {
            $depth = max(0, $depth - 1);
            continue;
        }
        if ($text === ',' && $depth === 0) {
            $segments[] = array_slice($tokens, $segmentStart, $index - $segmentStart);
            $segmentStart = $index + 1;
        }
    }

    $segments[] = array_slice($tokens, $segmentStart, $endIndex - $segmentStart);
    return $segments;
}

function segment_variable_name(array $segment): ?string {
    foreach ($segment as $token) {
        if (is_array($token) && $token[0] === T_VARIABLE) {
            return ltrim($token[1], '$');
        }
    }
    return null;
}

function segment_has_visibility(array $segment): bool {
    foreach ($segment as $token) {
        if (is_visibility_token($token)) {
            return true;
        }
    }
    return false;
}

function segment_has_optional_property_type(array $segment): bool {
    foreach ($segment as $token) {
        if (is_array($token) && $token[0] === T_VARIABLE) {
            return false;
        }
        $text = strtolower(token_text($token));
        if ($text === '?' || $text === 'null') {
            return true;
        }
    }
    return false;
}

function segment_is_optional_property(array $segment, bool $baseOptional = false): bool {
    if ($baseOptional || segment_has_optional_property_type($segment)) {
        return true;
    }

    $seenVariable = false;
    $seenEquals = false;
    foreach ($segment as $token) {
        $text = strtolower(token_text($token));
        if (is_array($token) && $token[0] === T_VARIABLE) {
            $seenVariable = true;
            continue;
        }
        if ($seenVariable && $text === '=') {
            $seenEquals = true;
            continue;
        }
        if ($seenEquals && $text === 'null') {
            return true;
        }
    }
    return false;
}

function promoted_properties(array $tokens, ?int $openIndex, ?int $closeIndex): array {
    if ($openIndex === null || $closeIndex === null || $closeIndex <= $openIndex + 1) {
        return [];
    }

    $properties = [];
    foreach (split_top_level_segments($tokens, $openIndex + 1, $closeIndex) as $segment) {
        if (!segment_has_visibility($segment)) {
            continue;
        }
        $name = segment_variable_name($segment);
        if ($name === null) {
            continue;
        }
        $properties[] = [
            'name' => $name,
            'is_optional' => segment_is_optional_property($segment),
        ];
    }
    return $properties;
}

function property_declaration_properties(array $tokens, int $startIndex): array {
    $count = count($tokens);
    $endIndex = $startIndex;
    for (; $endIndex < $count; $endIndex++) {
        $token = $tokens[$endIndex];
        if (is_array($token) && $token[0] === T_FUNCTION) {
            return [];
        }
        $text = token_text($token);
        if ($text === ';' || $text === '{') {
            break;
        }
    }

    $statement = array_slice($tokens, $startIndex, $endIndex - $startIndex);
    $baseOptional = segment_has_optional_property_type($statement);
    $properties = [];
    foreach (split_top_level_segments($tokens, $startIndex, $endIndex) as $segment) {
        $name = segment_variable_name($segment);
        if ($name === null) {
            continue;
        }
        $properties[] = [
            'name' => $name,
            'is_optional' => segment_is_optional_property($segment, $baseOptional),
        ];
    }
    return $properties;
}

function previous_significant_text(array $tokens, int $index): string {
    for ($j = $index - 1; $j >= 0; $j--) {
        $token = $tokens[$j];
        if (is_array($token) && in_array($token[0], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true)) {
            continue;
        }
        return token_text($token);
    }
    return '';
}

function previous_significant_token(array $tokens, int $index) {
    for ($j = $index - 1; $j >= 0; $j--) {
        $token = $tokens[$j];
        if (is_array($token) && in_array($token[0], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true)) {
            continue;
        }
        return $token;
    }
    return null;
}

function class_token_is_abstract(array $tokens, int $classIndex): bool {
    $token = previous_significant_token($tokens, $classIndex);
    return is_array($token) && $token[0] === T_ABSTRACT;
}

function member_is_abstract(array $tokens, int $functionIndex): bool {
    for ($index = $functionIndex - 1; $index >= 0; $index--) {
        $token = $tokens[$index];
        if (!is_array($token)) {
            $text = token_text($token);
            if ($text === ';' || $text === '{' || $text === '}') {
                break;
            }
            continue;
        }

        if (in_array($token[0], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT, T_PUBLIC, T_PROTECTED, T_PRIVATE, T_STATIC, T_FINAL], true)) {
            continue;
        }
        return $token[0] === T_ABSTRACT;
    }
    return false;
}

function source_export_entry(string $name, string $kind): array {
    return [
        'name' => $name,
        'local_name' => $name,
        'kind' => $kind,
        'crossing_type' => 'symbol',
        'path' => '',
        'is_relative' => false,
        'normalized_path' => '',
        'is_reexport' => false,
        'is_default' => false,
        'is_aliased' => false,
        'statement_id' => 0,
    ];
}

function collect_exports(array $classes, array $interfaces, array $abstractClasses, array $functions): array {
    $exports = [];
    foreach ($classes as $classDefinition) {
        $exports[] = source_export_entry($classDefinition['name'], 'class');
    }
    foreach ($interfaces as $interfaceDefinition) {
        $exports[] = source_export_entry($interfaceDefinition['name'], 'interface');
    }
    foreach ($abstractClasses as $classDefinition) {
        $exports[] = source_export_entry($classDefinition['name'], 'abstract_class');
    }
    foreach ($functions as $functionDefinition) {
        $exports[] = source_export_entry($functionDefinition['name'], 'function');
    }
    return $exports;
}

function source_id_for_path(string $path, string $sourcesRoot): string {
    $normalizedPath = str_replace('\\', '/', realpath($path) ?: $path);
    $normalizedRoot = rtrim(str_replace('\\', '/', realpath($sourcesRoot) ?: $sourcesRoot), '/');
    if ($normalizedRoot !== '' && str_starts_with($normalizedPath, $normalizedRoot . '/')) {
        $normalizedPath = substr($normalizedPath, strlen($normalizedRoot) + 1);
    }
    if (str_ends_with($normalizedPath, '.php')) {
        $normalizedPath = substr($normalizedPath, 0, -4);
    }
    return trim($normalizedPath, '/');
}

function line_number_at_offset(string $content, int $offset): int {
    return substr_count(substr($content, 0, max(0, $offset)), "\n") + 1;
}

function line_span_for_offsets(string $content, int $startOffset, int $endOffset): int {
    return line_number_at_offset($content, $endOffset) - line_number_at_offset($content, $startOffset) + 1;
}

function find_matching_text(string $content, int $openOffset, string $open, string $close): int {
    $depth = 0;
    $length = strlen($content);
    $inSingle = false;
    $inDouble = false;
    $inLineComment = false;
    $inBlockComment = false;
    for ($index = $openOffset; $index < $length; $index++) {
        $current = $content[$index];
        $next = $content[$index + 1] ?? '';
        if ($inLineComment) {
            if ($current === "\n") {
                $inLineComment = false;
            }
            continue;
        }
        if ($inBlockComment) {
            if ($current === '*' && $next === '/') {
                $inBlockComment = false;
                $index++;
            }
            continue;
        }
        if ($inSingle) {
            if ($current === '\\') {
                $index++;
                continue;
            }
            if ($current === "'") {
                $inSingle = false;
            }
            continue;
        }
        if ($inDouble) {
            if ($current === '\\') {
                $index++;
                continue;
            }
            if ($current === '"') {
                $inDouble = false;
            }
            continue;
        }
        if ($current === '/' && $next === '/') {
            $inLineComment = true;
            $index++;
            continue;
        }
        if ($current === '/' && $next === '*') {
            $inBlockComment = true;
            $index++;
            continue;
        }
        if ($current === "'") {
            $inSingle = true;
            continue;
        }
        if ($current === '"') {
            $inDouble = true;
            continue;
        }
        if ($current === $open) {
            $depth++;
            continue;
        }
        if ($current === $close) {
            $depth--;
            if ($depth === 0) {
                return $index;
            }
        }
    }
    return $openOffset;
}

function find_semicolon_text(string $content, int $startOffset): int {
    $length = strlen($content);
    for ($index = $startOffset; $index < $length; $index++) {
        if ($content[$index] === ';') {
            return $index;
        }
    }
    return max(0, $length - 1);
}

function callable_id_for_source(string $sourceId, string $qualifiedName): string {
    return $sourceId . '::' . $qualifiedName;
}

function parameter_definitions_from_text(string $parameterText): array {
    $parameters = [];
    foreach (explode(',', trim($parameterText)) as $rawParameter) {
        $parameter = trim($rawParameter);
        if ($parameter === '') {
            continue;
        }
        if (!preg_match('/\$([A-Za-z_][A-Za-z0-9_]*)/', $parameter, $match)) {
            continue;
        }
        $parameters[] = [
            'name' => $match[1],
            'annotation' => '',
            'kind' => str_contains($parameter, '...') ? 'vararg' : 'positional',
            'has_default' => str_contains($parameter, '=') || str_contains($parameter, '...'),
        ];
    }
    return $parameters;
}

function source_callable_entry(
    string $sourceId,
    string $name,
    string $qualifiedName,
    string $ownerName,
    string $kind,
    string $visibility,
    string $content,
    int $startOffset,
    int $endOffset,
    array $parameters
): array {
    return [
        'id' => callable_id_for_source($sourceId, $qualifiedName),
        'source_id' => $sourceId,
        'name' => $name,
        'qualified_name' => $qualifiedName,
        'owner_name' => $ownerName,
        'kind' => $kind,
        'visibility' => $visibility,
        'visibility_intent' => visibility_intent($name, $visibility),
        'line_start' => line_number_at_offset($content, $startOffset),
        'line_end' => line_number_at_offset($content, $endOffset),
        'line_count' => line_span_for_offsets($content, $startOffset, $endOffset),
        'parameters' => $parameters,
        'declared_args' => count($parameters),
        'optional_args' => count(array_filter($parameters, fn ($parameter) => $parameter['has_default'])),
        'return_annotation' => '',
        'decorators' => [],
        'docstring' => '',
    ];
}

function source_value_entry(
    string $name,
    string $visibility,
    string $content,
    int $startOffset,
    int $endOffset,
    string $valueKind,
    array $parameters = []
): array {
    return [
        'name' => $name,
        'visibility' => $visibility,
        'visibility_intent' => visibility_intent($name, $visibility),
        'line_count' => line_span_for_offsets($content, $startOffset, $endOffset),
        'declaration_kind' => 'assignment',
        'value_kind' => $valueKind,
        'declared_args' => count($parameters),
        'optional_args' => count(array_filter($parameters, fn ($parameter) => $parameter['has_default'])),
    ];
}

function offset_within_ranges(int $offset, array $ranges): bool {
    foreach ($ranges as $range) {
        if ($offset >= $range['start'] && $offset <= $range['end']) {
            return true;
        }
    }
    return false;
}

function collect_callable_graph(string $content, string $sourceId): array {
    $values = [];
    $callables = [];
    $callableRanges = [];
    $classRanges = [];

    if (preg_match_all('/\bclass\s+([A-Za-z_][A-Za-z0-9_]*)[^{]*\{/', $content, $classMatches, PREG_OFFSET_CAPTURE)) {
        foreach ($classMatches[0] as $index => $fullMatch) {
            $className = $classMatches[1][$index][0];
            $classStart = $fullMatch[1];
            $classOpen = strpos($content, '{', $classStart);
            if ($classOpen === false) {
                continue;
            }
            $classEnd = find_matching_text($content, $classOpen, '{', '}');
            $classRanges[] = ['start' => $classStart, 'end' => $classEnd];
            $body = substr($content, $classOpen + 1, $classEnd - $classOpen - 1);
            if (!preg_match_all('/((?:public|protected|private|static|final|abstract|\s)+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)[^{;]*(\{|;)/', $body, $methodMatches, PREG_OFFSET_CAPTURE)) {
                continue;
            }
            foreach ($methodMatches[0] as $methodIndex => $methodFullMatch) {
                if ($methodMatches[4][$methodIndex][0] !== '{') {
                    continue;
                }
                $prefix = $methodMatches[1][$methodIndex][0] ?? '';
                $methodName = $methodMatches[2][$methodIndex][0];
                $parameters = parameter_definitions_from_text($methodMatches[3][$methodIndex][0]);
                $methodStart = $classOpen + 1 + $methodFullMatch[1];
                $methodOpen = strpos($content, '{', $methodStart);
                if ($methodOpen === false) {
                    continue;
                }
                $methodEnd = find_matching_text($content, $methodOpen, '{', '}');
                $visibility = 'public';
                if (str_contains($prefix, 'private')) {
                    $visibility = 'private';
                } elseif (str_contains($prefix, 'protected')) {
                    $visibility = 'protected';
                }
                $kind = $methodName === '__construct' ? 'constructor' : (str_contains($prefix, 'static') ? 'staticmethod' : 'method');
                $qualifiedName = $className . '.' . $methodName;
                $callable = source_callable_entry(
                    $sourceId,
                    $methodName,
                    $qualifiedName,
                    $className,
                    $kind,
                    $visibility,
                    $content,
                    $methodStart,
                    $methodEnd,
                    $parameters
                );
                $callables[] = $callable;
                $callableRanges[] = [
                    'id' => $callable['id'],
                    'owner_name' => $className,
                    'body_start' => $methodOpen + 1,
                    'body_end' => $methodEnd,
                ];
            }
        }
    }

    if (preg_match_all('/\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)[^{;]*\{/', $content, $functionMatches, PREG_OFFSET_CAPTURE)) {
        foreach ($functionMatches[0] as $index => $fullMatch) {
            $functionStart = $fullMatch[1];
            if (offset_within_ranges($functionStart, $classRanges)) {
                continue;
            }
            $functionName = $functionMatches[1][$index][0];
            $parameters = parameter_definitions_from_text($functionMatches[2][$index][0]);
            $functionOpen = strpos($content, '{', $functionStart);
            if ($functionOpen === false) {
                continue;
            }
            $functionEnd = find_matching_text($content, $functionOpen, '{', '}');
            $callable = source_callable_entry(
                $sourceId,
                $functionName,
                $functionName,
                '',
                'function',
                'public',
                $content,
                $functionStart,
                $functionEnd,
                $parameters
            );
            $callables[] = $callable;
            $callableRanges[] = [
                'id' => $callable['id'],
                'owner_name' => '',
                'body_start' => $functionOpen + 1,
                'body_end' => $functionEnd,
            ];
        }
    }

    if (preg_match_all('/\$([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(function|fn)\s*\(([^)]*)\)/', $content, $valueMatches, PREG_OFFSET_CAPTURE)) {
        foreach ($valueMatches[0] as $index => $fullMatch) {
            $name = $valueMatches[1][$index][0];
            $callableType = $valueMatches[2][$index][0];
            $parameters = parameter_definitions_from_text($valueMatches[3][$index][0]);
            $start = $fullMatch[1];
            $end = find_semicolon_text($content, $start);
            if ($callableType === 'function') {
                $open = strpos($content, '{', $start);
                if ($open !== false && $open < $end) {
                    $end = find_matching_text($content, $open, '{', '}');
                }
            }
            $values[] = source_value_entry($name, 'public', $content, $start, $end, 'callable', $parameters);
            $callable = source_callable_entry(
                $sourceId,
                $name,
                $name,
                '',
                'callable_value',
                'public',
                $content,
                $start,
                $end,
                $parameters
            );
            $callables[] = $callable;
            $callableRanges[] = [
                'id' => $callable['id'],
                'owner_name' => '',
                'body_start' => $callableType === 'function' && isset($open) && $open !== false ? $open + 1 : $start,
                'body_end' => $end,
            ];
        }
    }

    if (preg_match_all('/\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*=/', $content, $constMatches, PREG_OFFSET_CAPTURE)) {
        foreach ($constMatches[0] as $index => $fullMatch) {
            $start = $fullMatch[1];
            $end = find_semicolon_text($content, $start);
            $values[] = source_value_entry($constMatches[1][$index][0], 'public', $content, $start, $end, 'unknown');
        }
    }

    $anonymousCallables = [];
    $anonymousRanges = [];
    foreach ($callableRanges as $parentRange) {
        $body = substr($content, $parentRange['body_start'], $parentRange['body_end'] - $parentRange['body_start']);
        if (!preg_match_all('/(?<![A-Za-z0-9_])(?:function|fn)\s*\(([^)]*)\)/', $body, $anonymousMatches, PREG_OFFSET_CAPTURE)) {
            continue;
        }
        foreach ($anonymousMatches[0] as $index => $fullMatch) {
            $start = $parentRange['body_start'] + $fullMatch[1];
            if (preg_match('/\$[A-Za-z_][A-Za-z0-9_]*\s*=\s*$/', substr($content, max(0, $start - 64), 64))) {
                continue;
            }
            $end = find_semicolon_text($content, $start);
            $open = strpos($content, '{', $start);
            if ($open !== false && $open < $end) {
                $end = find_matching_text($content, $open, '{', '}');
            }
            $bodyText = substr($content, $open !== false && $open < $end ? $open + 1 : $start, $end - $start);
            if (!preg_match('/[A-Za-z_][A-Za-z0-9_]*\s*\(/', $bodyText)) {
                continue;
            }
            $line = line_number_at_offset($content, $start);
            $column = $start - strrpos(substr($content, 0, $start), "\n");
            $name = '<anonymous>@' . $line . ':' . $column;
            $parentQualifiedName = explode('::', $parentRange['id'], 2)[1] ?? '';
            $callable = source_callable_entry(
                $sourceId,
                $name,
                $parentQualifiedName . '.' . $name,
                $parentRange['owner_name'],
                'anonymous',
                'public',
                $content,
                $start,
                $end,
                parameter_definitions_from_text($anonymousMatches[1][$index][0])
            );
            $anonymousCallables[] = $callable;
            $anonymousRanges[] = [
                'id' => $callable['id'],
                'owner_name' => $parentRange['owner_name'],
                'body_start' => $open !== false && $open < $end ? $open + 1 : $start,
                'body_end' => $end,
            ];
        }
    }
    $callables = array_merge($callables, $anonymousCallables);
    $callableRanges = array_merge($callableRanges, $anonymousRanges);

    return [
        'values' => $values,
        'callables' => $callables,
        'calls' => collect_source_calls($content, $sourceId, $callables, $callableRanges),
    ];
}

function collect_source_calls(string $content, string $sourceId, array $callables, array $callableRanges): array {
    $byName = [];
    $byQualifiedName = [];
    $constructorsByName = [];
    foreach ($callables as $callable) {
        $byQualifiedName[$callable['qualified_name']] = $callable['id'];
        if (in_array($callable['kind'], ['function', 'callable_value'], true)) {
            $byName[$callable['name']] = $callable['id'];
        }
        if ($callable['kind'] === 'constructor') {
            $constructorsByName[$callable['owner_name']] = $callable['id'];
        }
    }

    $calls = [];
    $ignored = ['if', 'for', 'foreach', 'while', 'switch', 'catch', 'function', 'fn', 'echo', 'return'];
    foreach ($callableRanges as $range) {
        $body = substr($content, $range['body_start'], $range['body_end'] - $range['body_start']);
        if (!preg_match_all('/\b(new\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(|(?:\$this->|self::|static::)([A-Za-z_][A-Za-z0-9_]*)\s*\(/', $body, $matches, PREG_OFFSET_CAPTURE)) {
            continue;
        }
        foreach ($matches[0] as $index => $fullMatch) {
            $absoluteOffset = $range['body_start'] + $fullMatch[1];
            $isConstructor = ($matches[1][$index][0] ?? '') !== '';
            $name = $matches[2][$index][0] ?: $matches[3][$index][0];
            if (in_array($name, $ignored, true)) {
                continue;
            }
            $targetCallableId = '';
            $resolution = 'unresolved';
            if ($isConstructor && array_key_exists($name, $constructorsByName)) {
                $targetCallableId = $constructorsByName[$name];
                $resolution = 'resolved';
            } elseif (($matches[3][$index][0] ?? '') !== '' && $range['owner_name'] !== '') {
                $qualifiedName = $range['owner_name'] . '.' . $name;
                if (array_key_exists($qualifiedName, $byQualifiedName)) {
                    $targetCallableId = $byQualifiedName[$qualifiedName];
                    $resolution = 'resolved';
                }
            } elseif (array_key_exists($name, $byName)) {
                $targetCallableId = $byName[$name];
                $resolution = 'resolved';
            }
            $calls[] = [
                'source_callable_id' => $range['id'],
                'target_callable_id' => $targetCallableId,
                'source_id' => $sourceId,
                'line' => line_number_at_offset($content, $absoluteOffset),
                'expression' => $name,
                'resolution' => $resolution,
                'target_name' => $name,
            ];
        }
    }
    return $calls;
}

function extract_file(string $path, ?string $sourceId = null, string $sourcesRoot = ''): array {
    $content = file_get_contents($path);
    $resolvedSourceId = $sourceId ?? source_id_for_path($path, $sourcesRoot !== '' ? $sourcesRoot : dirname($path));
    $tokens = token_get_all($content);
    $imports = [];
    $classes = [];
    $interfaces = [];
    $types = [];
    $abstractClasses = [];
    $functions = [];
    $classIndexByName = [];
    $interfaceIndexByName = [];
    $abstractClassIndexByName = [];

    $count = count($tokens);
    $currentLine = 1;
    $braceDepth = 0;
    $activeDefinitionKind = null;
    $activeDefinitionName = null;
    $activeDefinitionDepth = 0;
    $statementId = 0;

    for ($i = 0; $i < $count; $i++) {
        $token = $tokens[$i];
        $currentLine = token_line_value($token, $currentLine);

        if ($token === '{') {
            $braceDepth++;
            continue;
        }
        if ($token === '}') {
            if ($activeDefinitionName !== null && $braceDepth === $activeDefinitionDepth) {
                $activeDefinitionKind = null;
                $activeDefinitionName = null;
                $activeDefinitionDepth = 0;
            }
            $braceDepth = max(0, $braceDepth - 1);
            continue;
        }
        if (!is_array($token)) {
            continue;
        }

        if ($token[0] === T_USE) {
            $statementId++;
            $imports = array_merge(
                $imports,
                use_statement_imports($tokens, $i, $statementId),
            );
            continue;
        }

        if ($token[0] === T_CLASS) {
            $j = $i + 1;
            while ($j < $count && token_text($tokens[$j]) !== '{') {
                if (is_array($tokens[$j]) && $tokens[$j][0] === T_STRING) {
                    $className = $tokens[$j][1];
                    if (class_token_is_abstract($tokens, $i)) {
                        $abstractClasses[] = [
                            'name' => $className,
                            'visibility' => 'public',
                            'visibility_intent' => visibility_intent($className, 'public'),
                            'abstract_methods' => [],
                            'concrete_methods' => [],
                            'properties' => [],
                            'line_count' => max(
                                0,
                                find_block_end_line($tokens, $j, $currentLine) - $currentLine + 1
                            ),
                        ];
                        $abstractClassIndexByName[$className] = count($abstractClasses) - 1;
                        $activeDefinitionKind = 'abstract_class';
                    } else {
                        $classes[] = [
                            'name' => $className,
                            'visibility' => 'public',
                            'visibility_intent' => visibility_intent($className, 'public'),
                            'methods' => [],
                            'properties' => [],
                            'line_count' => max(
                                0,
                                find_block_end_line($tokens, $j, $currentLine) - $currentLine + 1
                            ),
                        ];
                        $classIndexByName[$className] = count($classes) - 1;
                        $activeDefinitionKind = 'class';
                    }
                    $activeDefinitionName = $className;
                    $activeDefinitionDepth = $braceDepth + 1;
                    break;
                }
                $j++;
            }
            continue;
        }

        if ($token[0] === T_INTERFACE) {
            $j = $i + 1;
            while ($j < $count && token_text($tokens[$j]) !== '{') {
                if (is_array($tokens[$j]) && $tokens[$j][0] === T_STRING) {
                    $interfaceName = $tokens[$j][1];
                    $interfaces[] = [
                        'name' => $interfaceName,
                        'visibility' => 'public',
                        'visibility_intent' => visibility_intent($interfaceName, 'public'),
                        'methods' => [],
                        'properties' => [],
                        'signatures' => [],
                        'line_count' => max(
                            0,
                            find_block_end_line($tokens, $j, $currentLine) - $currentLine + 1
                        ),
                    ];
                    $interfaceIndexByName[$interfaceName] = count($interfaces) - 1;
                    $activeDefinitionKind = 'interface';
                    $activeDefinitionName = $interfaceName;
                    $activeDefinitionDepth = $braceDepth + 1;
                    break;
                }
                $j++;
            }
            continue;
        }

        if (
            $activeDefinitionName !== null
            && in_array($activeDefinitionKind, ['class', 'abstract_class'], true)
            && $braceDepth === $activeDefinitionDepth
            && is_visibility_token($token)
            && !in_array(previous_significant_text($tokens, $i), ['(', ','], true)
        ) {
            $definitionIndex = $activeDefinitionKind === 'class'
                ? $classIndexByName[$activeDefinitionName]
                : $abstractClassIndexByName[$activeDefinitionName];
            foreach (property_declaration_properties($tokens, $i) as $property) {
                if ($activeDefinitionKind === 'class') {
                    add_class_property(
                        $classes[$definitionIndex],
                        $property['name'],
                        $property['is_optional']
                    );
                } else {
                    add_class_property(
                        $abstractClasses[$definitionIndex],
                        $property['name'],
                        $property['is_optional']
                    );
                }
            }
            continue;
        }

        if ($token[0] === T_FUNCTION) {
            $j = $i + 1;
            while ($j < $count && token_text($tokens[$j]) !== '(') {
                if (is_array($tokens[$j]) && $tokens[$j][0] === T_STRING) {
                    $functionName = $tokens[$j][1];
                    $lineCount = max(
                        0,
                        find_block_end_line($tokens, $j, $currentLine) - $currentLine + 1
                    );
                    [$openIndex, $closeIndex] = find_parameter_bounds($tokens, $i);
                    $parameterCounts = parameter_counts($tokens, $openIndex, $closeIndex);
                    if ($activeDefinitionKind === 'class' && $activeDefinitionName !== null && array_key_exists($activeDefinitionName, $classIndexByName)) {
                        if ($functionName === '__construct') {
                            foreach (promoted_properties($tokens, $openIndex, $closeIndex) as $property) {
                                add_class_property(
                                    $classes[$classIndexByName[$activeDefinitionName]],
                                    $property['name'],
                                    $property['is_optional']
                                );
                            }
                        }
                        $visibility = member_visibility($tokens, $i);
                        $classes[$classIndexByName[$activeDefinitionName]]['methods'][] = [
                            'name' => $functionName,
                            'visibility' => $visibility,
                            'visibility_intent' => visibility_intent($functionName, $visibility),
                            'line_count' => $lineCount,
                            'declared_args' => $parameterCounts['declared_args'],
                            'optional_args' => $parameterCounts['optional_args'],
                        ];
                    } elseif ($activeDefinitionKind === 'abstract_class' && $activeDefinitionName !== null && array_key_exists($activeDefinitionName, $abstractClassIndexByName)) {
                        if ($functionName === '__construct') {
                            foreach (promoted_properties($tokens, $openIndex, $closeIndex) as $property) {
                                add_class_property(
                                    $abstractClasses[$abstractClassIndexByName[$activeDefinitionName]],
                                    $property['name'],
                                    $property['is_optional']
                                );
                            }
                        }
                        $visibility = member_visibility($tokens, $i);
                        $methodDefinition = [
                            'name' => $functionName,
                            'visibility' => $visibility,
                            'visibility_intent' => visibility_intent($functionName, $visibility),
                            'line_count' => $lineCount,
                            'declared_args' => $parameterCounts['declared_args'],
                            'optional_args' => $parameterCounts['optional_args'],
                        ];
                        if (member_is_abstract($tokens, $i)) {
                            $abstractClasses[$abstractClassIndexByName[$activeDefinitionName]]['abstract_methods'][] = $methodDefinition;
                        } else {
                            $abstractClasses[$abstractClassIndexByName[$activeDefinitionName]]['concrete_methods'][] = $methodDefinition;
                        }
                    } elseif ($activeDefinitionKind === 'interface' && $activeDefinitionName !== null && array_key_exists($activeDefinitionName, $interfaceIndexByName)) {
                        $visibility = member_visibility($tokens, $i);
                        $interfaces[$interfaceIndexByName[$activeDefinitionName]]['methods'][] = [
                            'name' => $functionName,
                            'visibility' => $visibility,
                            'visibility_intent' => visibility_intent($functionName, $visibility),
                            'line_count' => $lineCount,
                            'declared_args' => $parameterCounts['declared_args'],
                            'optional_args' => $parameterCounts['optional_args'],
                        ];
                    } else {
                        $functions[] = [
                            'name' => $functionName,
                            'visibility' => 'public',
                            'visibility_intent' => visibility_intent($functionName, 'public'),
                            'line_count' => $lineCount,
                            'declared_args' => $parameterCounts['declared_args'],
                            'optional_args' => $parameterCounts['optional_args'],
                        ];
                    }
                    break;
                }
                $j++;
            }
        }
    }

    $publicMethodCounts = array_map(
        fn ($classDefinition) => count(array_filter(
            $classDefinition['methods'],
            fn ($methodDefinition) => $methodDefinition['visibility'] === 'public',
        )),
        $classes
    );
    $publicAbstractClassMethodCounts = array_map(
        fn ($classDefinition) => count(array_filter(
            array_merge($classDefinition['abstract_methods'], $classDefinition['concrete_methods']),
            fn ($methodDefinition) => $methodDefinition['visibility'] === 'public',
        )),
        $abstractClasses
    );

    $callableGraph = collect_callable_graph($content, $resolvedSourceId);

    return [
        'imports' => $imports,
        'exports' => collect_exports($classes, $interfaces, $abstractClasses, $functions),
        'classes' => $classes,
        'interfaces' => $interfaces,
        'types' => $types,
        'abstract_classes' => $abstractClasses,
        'functions' => $functions,
        'values' => $callableGraph['values'],
        'callables' => $callableGraph['callables'],
        'calls' => $callableGraph['calls'],
        'line_count' => line_count_for_content($content),
        'code_line_count' => code_line_count_for_content($content),
        'public_symbol_count' => count($classes) + count($interfaces) + count($abstractClasses) + count($functions) + array_sum($publicMethodCounts) + array_sum($publicAbstractClassMethodCounts),
    ];
}

function extract_batch_from_stdin(string $sourcesRoot): array {
    $payload = stream_get_contents(STDIN);
    $pathsBySourceId = json_decode($payload, true);
    if (!is_array($pathsBySourceId)) {
        fwrite(STDERR, "Expected a JSON object mapping source ids to PHP file paths.\n");
        exit(1);
    }

    $result = [];
    foreach ($pathsBySourceId as $sourceId => $path) {
        if (!is_string($sourceId) || !is_string($path)) {
            fwrite(STDERR, "Expected source ids and paths to be strings.\n");
            exit(1);
        }
        $result[$sourceId] = extract_file($path, $sourceId, $sourcesRoot);
    }
    return $result;
}

function write_batch_jsonl_from_stdin(string $sourcesRoot): void {
    $payload = stream_get_contents(STDIN);
    $pathsBySourceId = json_decode($payload, true);
    if (!is_array($pathsBySourceId)) {
        fwrite(STDERR, "Expected a JSON object mapping source ids to PHP file paths.\n");
        exit(1);
    }

    foreach ($pathsBySourceId as $sourceId => $path) {
        if (!is_string($sourceId) || !is_string($path)) {
            fwrite(STDERR, "Expected source ids and paths to be strings.\n");
            exit(1);
        }
        echo json_encode([
            $sourceId,
            extract_file($path, $sourceId, $sourcesRoot),
        ]) . "\n";
    }
}

if (($argv[1] ?? null) === '--batch') {
    if (in_array('--jsonl', $argv, true)) {
        write_batch_jsonl_from_stdin($argv[2] ?? getcwd());
    } else {
        echo json_encode(extract_batch_from_stdin($argv[2] ?? getcwd()));
    }
} else {
    echo json_encode(extract_file($argv[1], null, $argv[2] ?? dirname($argv[1])));
}
