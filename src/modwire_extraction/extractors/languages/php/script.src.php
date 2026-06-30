#!/usr/bin/env php
<?php

declare(strict_types=1);

require __DIR__ . '/vendor/autoload.php';

use PhpParser\Error;
use PhpParser\Node;
use PhpParser\Node\Arg;
use PhpParser\Node\Expr;
use PhpParser\Node\Name;
use PhpParser\Node\Param;
use PhpParser\Node\Stmt;
use PhpParser\ParserFactory;

function line_count_for_content(string $content): int {
    return max(1, substr_count($content, "\n") + 1);
}

function code_line_count_for_content(string $content): int {
    $count = 0;
    foreach (explode("\n", $content) as $line) {
        $trimmed = trim($line);
        if (
            $trimmed !== ''
            && !str_starts_with($trimmed, '//')
            && !str_starts_with($trimmed, '#')
            && !str_starts_with($trimmed, '/*')
            && !str_starts_with($trimmed, '*')
        ) {
            $count++;
        }
    }
    return $count;
}

function source_id_for_path(string $path, string $sourcesRoot): string {
    $normalizedPath = str_replace('\\', '/', realpath($path) ?: $path);
    $normalizedRoot = rtrim(str_replace('\\', '/', realpath($sourcesRoot) ?: $sourcesRoot), '/');
    if ($normalizedRoot !== '' && str_starts_with($normalizedPath, $normalizedRoot . '/')) {
        $normalizedPath = substr($normalizedPath, strlen($normalizedRoot) + 1);
    }
    return trim(preg_replace('/\.php$/', '', $normalizedPath), '/');
}

function line_span(Node $node): int {
    return max(1, $node->getEndLine() - $node->getStartLine() + 1);
}

function visibility_intent(string $name, string $visibility): string {
    $magicMethods = [
        '__call', '__callStatic', '__clone', '__construct', '__debugInfo', '__destruct',
        '__get', '__invoke', '__isset', '__serialize', '__set', '__set_state', '__sleep',
        '__toString', '__unserialize', '__unset', '__wakeup',
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

function node_name(Node|Name|string|null $node): string {
    if ($node instanceof Name) {
        return $node->toString();
    }
    if ($node instanceof Node\Identifier || $node instanceof Node\VarLikeIdentifier) {
        return $node->toString();
    }
    if (is_string($node)) {
        return $node;
    }
    return '';
}

function var_name(Expr $expr): string {
    return $expr instanceof Expr\Variable && is_string($expr->name) ? $expr->name : '';
}

function normalize_import_path(string $value): string {
    return trim(str_replace('\\', '/', $value), '/ ');
}

function import_parent_path(string $value): string {
    $parts = explode('/', normalize_import_path($value));
    array_pop($parts);
    return implode('/', $parts);
}

function imported_symbol_name(string $path): string {
    $parts = explode('/', normalize_import_path($path));
    return end($parts) ?: '';
}

function walk_nodes(array $nodes, callable $callback, array $parents = []): void {
    foreach ($nodes as $node) {
        if (!$node instanceof Node) {
            continue;
        }
        $callback($node, $parents);
        $nextParents = [...$parents, $node];
        foreach ($node->getSubNodeNames() as $name) {
            $child = $node->{$name};
            if ($child instanceof Node) {
                walk_nodes([$child], $callback, $nextParents);
            } elseif (is_array($child)) {
                walk_nodes($child, $callback, $nextParents);
            }
        }
    }
}

function nearest_parent(array $parents, string ...$classes): ?Node {
    for ($index = count($parents) - 1; $index >= 0; $index--) {
        foreach ($classes as $class) {
            if ($parents[$index] instanceof $class) {
                return $parents[$index];
            }
        }
    }
    return null;
}

function is_top_level(array $parents): bool {
    foreach ($parents as $parent) {
        if (!$parent instanceof Stmt\Namespace_) {
            return false;
        }
    }
    return true;
}

function function_parent(array $parents): ?Node {
    return nearest_parent(
        $parents,
        Stmt\ClassMethod::class,
        Stmt\Function_::class,
        Expr\Closure::class,
        Expr\ArrowFunction::class,
    );
}

function class_visibility(Stmt\ClassLike $node): string {
    return 'public';
}

function member_visibility(Stmt\ClassMethod|Stmt\Property|Stmt\ClassConst $node): string {
    if ($node->isPrivate()) {
        return 'private';
    }
    if ($node->isProtected()) {
        return 'protected';
    }
    return 'public';
}

function parameter_definitions(array $params): array {
    return array_map(fn (Param $param): array => [
        'name' => var_name($param->var),
        'annotation' => $param->type instanceof Node ? node_name($param->type) : '',
        'kind' => $param->variadic ? 'vararg' : 'positional',
        'has_default' => $param->default !== null || $param->variadic,
    ], $params);
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

function source_callable_entry(
    string $sourceId,
    string $name,
    string $qualifiedName,
    string $ownerName,
    string $kind,
    string $visibility,
    Node $node,
    array $parameters,
    string $returnAnnotation = ''
): array {
    return [
        'id' => $sourceId . '::' . $qualifiedName,
        'source_id' => $sourceId,
        'name' => $name,
        'qualified_name' => $qualifiedName,
        'owner_name' => $ownerName,
        'kind' => $kind,
        'visibility' => $visibility,
        'visibility_intent' => visibility_intent($name, $visibility),
        'line_start' => $node->getStartLine(),
        'line_end' => $node->getEndLine(),
        'line_count' => line_span($node),
        'parameters' => $parameters,
        'declared_args' => count($parameters),
        'optional_args' => count(array_filter($parameters, fn (array $parameter): bool => $parameter['has_default'])),
        'return_annotation' => $returnAnnotation,
        'decorators' => [],
        'docstring' => '',
    ];
}

function source_value_entry(
    string $name,
    string $visibility,
    Node $node,
    string $declarationKind,
    string $valueKind,
    array $parameters = []
): array {
    return [
        'name' => $name,
        'visibility' => $visibility,
        'visibility_intent' => visibility_intent($name, $visibility),
        'line_count' => line_span($node),
        'declaration_kind' => $declarationKind,
        'value_kind' => $valueKind,
        'declared_args' => count($parameters),
        'optional_args' => count(array_filter($parameters, fn (array $parameter): bool => $parameter['has_default'])),
    ];
}

function value_kind(?Expr $expr): string {
    if ($expr === null) {
        return 'unknown';
    }
    if ($expr instanceof Expr\Closure || $expr instanceof Expr\ArrowFunction) {
        return 'callable';
    }
    if ($expr instanceof Expr\New_ || $expr instanceof Expr\Array_) {
        return 'object';
    }
    if ($expr instanceof Node\Scalar || $expr instanceof Expr\ConstFetch) {
        return 'literal';
    }
    return 'unknown';
}

function expr_name(Expr|Name|Node\Identifier|null $expr): string {
    if ($expr instanceof Name || $expr instanceof Node\Identifier) {
        return node_name($expr);
    }
    if ($expr instanceof Expr\Variable) {
        return '$' . var_name($expr);
    }
    if ($expr instanceof Expr\PropertyFetch) {
        return expr_name($expr->var) . '->' . node_name($expr->name);
    }
    if ($expr instanceof Expr\StaticPropertyFetch) {
        return expr_name($expr->class) . '::$' . node_name($expr->name);
    }
    if ($expr instanceof Expr\MethodCall) {
        return expr_name($expr->var) . '->' . node_name($expr->name);
    }
    if ($expr instanceof Expr\StaticCall) {
        return expr_name($expr->class) . '::' . node_name($expr->name);
    }
    if ($expr instanceof Expr\FuncCall) {
        return expr_name($expr->name);
    }
    if ($expr instanceof Expr\New_) {
        return expr_name($expr->class);
    }
    return '';
}

function expression_target_name(string $expression): string {
    if (str_contains($expression, '->')) {
        $parts = explode('->', $expression);
        return end($parts) ?: $expression;
    }
    if (str_contains($expression, '::')) {
        $parts = explode('::', $expression);
        return ltrim(end($parts) ?: $expression, '$');
    }
    return trim($expression, '$\\');
}

function collect_imports(array $nodes): array {
    $imports = [];
    $statementId = 0;

    walk_nodes($nodes, function (Node $node, array $parents) use (&$imports, &$statementId): void {
        if (!$node instanceof Stmt\Use_ && !$node instanceof Stmt\GroupUse) {
            return;
        }
        if (!is_top_level($parents)) {
            return;
        }

        $statementId++;
        $prefix = $node instanceof Stmt\GroupUse ? node_name($node->prefix) . '\\' : '';
        foreach ($node->uses as $use) {
            $path = trim($prefix . node_name($use->name), '\\');
            $alias = $use->alias !== null ? node_name($use->alias) : '';
            $symbolName = imported_symbol_name($path);
            $imports[] = [
                'path' => $path,
                'is_relative' => false,
                'normalized_path' => normalize_import_path($path),
                'imported_name' => '',
                'is_aliased' => $alias !== '',
                'crossing_type' => 'symbol',
                'file_barrier_crossed' => true,
                'statement_id' => $statementId,
                'join_key' => import_parent_path($path),
                'uses_joined_import' => count($node->uses) > 1,
                'imported_symbols' => [[
                    'name' => $symbolName,
                    'alias' => $alias,
                    'is_aliased' => $alias !== '',
                    'is_default' => false,
                    'is_namespace' => false,
                    'is_star' => false,
                ]],
            ];
        }
    });

    return $imports;
}

function collect_definitions(array $nodes, string $sourceId): array {
    $classes = [];
    $interfaces = [];
    $abstractClasses = [];
    $functions = [];
    $exports = [];
    $classNames = [];

    walk_nodes($nodes, function (Node $node, array $parents) use (
        &$classes,
        &$interfaces,
        &$abstractClasses,
        &$functions,
        &$exports,
        &$classNames
    ): void {
        if ($node instanceof Stmt\Class_ && $node->name !== null && function_parent($parents) === null) {
            $name = node_name($node->name);
            $classNames[spl_object_id($node)] = $name;
            $properties = [];
            foreach ($node->getProperties() as $property) {
                foreach ($property->props as $propertyProperty) {
                    $properties[$propertyProperty->name->toString()] = [
                        'name' => $propertyProperty->name->toString(),
                        'is_optional' => $propertyProperty->default instanceof Expr\ConstFetch
                            && strtolower(node_name($propertyProperty->default->name)) === 'null',
                    ];
                }
            }
            foreach ($node->getMethods() as $method) {
                if ($method->name->toString() !== '__construct') {
                    continue;
                }
                foreach ($method->params as $param) {
                    if (($param->flags ?? 0) !== 0) {
                        $propertyName = var_name($param->var);
                        $properties[$propertyName] = [
                            'name' => $propertyName,
                            'is_optional' => $param->default !== null,
                        ];
                    }
                }
            }
            $methods = [];
            $abstractMethods = [];
            $concreteMethods = [];
            foreach ($node->getMethods() as $method) {
                $methodName = $method->name->toString();
                $parameters = parameter_definitions($method->params);
                $entry = [
                    'name' => $methodName,
                    'visibility' => member_visibility($method),
                    'visibility_intent' => visibility_intent($methodName, member_visibility($method)),
                    'line_count' => line_span($method),
                    'declared_args' => count($parameters),
                    'optional_args' => count(array_filter($parameters, fn (array $parameter): bool => $parameter['has_default'])),
                ];
                if ($node->isAbstract()) {
                    if ($method->isAbstract()) {
                        $abstractMethods[] = $entry;
                    } else {
                        $concreteMethods[] = $entry;
                    }
                } else {
                    $methods[] = $entry;
                }
            }
            $base = [
                'name' => $name,
                'visibility' => class_visibility($node),
                'visibility_intent' => visibility_intent($name, class_visibility($node)),
                'properties' => array_values($properties),
                'line_count' => line_span($node),
            ];
            if ($node->isAbstract()) {
                $abstractClasses[] = [
                    ...$base,
                    'abstract_methods' => $abstractMethods,
                    'concrete_methods' => $concreteMethods,
                ];
                $exports[] = source_export_entry($name, 'abstract_class');
            } else {
                $classes[] = [
                    ...$base,
                    'methods' => $methods,
                ];
                $exports[] = source_export_entry($name, 'class');
            }
            return;
        }

        if ($node instanceof Stmt\Interface_ && function_parent($parents) === null) {
            $name = node_name($node->name);
            $methods = [];
            foreach ($node->getMethods() as $method) {
                $parameters = parameter_definitions($method->params);
                $methods[] = [
                    'name' => $method->name->toString(),
                    'visibility' => 'public',
                    'visibility_intent' => visibility_intent($method->name->toString(), 'public'),
                    'line_count' => line_span($method),
                    'declared_args' => count($parameters),
                    'optional_args' => count(array_filter($parameters, fn (array $parameter): bool => $parameter['has_default'])),
                ];
            }
            $interfaces[] = [
                'name' => $name,
                'visibility' => 'public',
                'visibility_intent' => visibility_intent($name, 'public'),
                'methods' => $methods,
                'properties' => [],
                'signatures' => [],
                'line_count' => line_span($node),
            ];
            $exports[] = source_export_entry($name, 'interface');
            return;
        }

        if ($node instanceof Stmt\Function_ && function_parent($parents) === null) {
            $name = node_name($node->name);
            $parameters = parameter_definitions($node->params);
            $functions[] = [
                'name' => $name,
                'visibility' => 'public',
                'visibility_intent' => visibility_intent($name, 'public'),
                'line_count' => line_span($node),
                'declared_args' => count($parameters),
                'optional_args' => count(array_filter($parameters, fn (array $parameter): bool => $parameter['has_default'])),
            ];
            $exports[] = source_export_entry($name, 'function');
        }
    });

    return [
        'classes' => $classes,
        'interfaces' => $interfaces,
        'types' => [],
        'abstract_classes' => $abstractClasses,
        'functions' => $functions,
        'exports' => $exports,
        'class_names' => $classNames,
    ];
}

function callable_name_for_expr(Expr\Closure|Expr\ArrowFunction $node, array $parents): array {
    $parent = $parents[count($parents) - 1] ?? null;
    if ($parent instanceof Expr\Assign && $parent->var instanceof Expr\Variable && is_string($parent->var->name)) {
        return [$parent->var->name, $parent->var->name, '', 'private', $parent];
    }
    if ($parent instanceof Arg) {
        $name = '<anonymous>@' . $node->getStartLine();
        return [$name, $name, '', 'private', $node];
    }
    $name = '<anonymous>@' . $node->getStartLine();
    return [$name, $name, '', 'private', $node];
}

function collect_values_and_callables(array $nodes, string $sourceId): array {
    $values = [];
    $callables = [];
    $callableRanges = [];
    $seenCallables = [];

    $addCallable = function (array $entry, Node $node) use (&$callables, &$callableRanges, &$seenCallables): void {
        $baseQualifiedName = $entry['qualified_name'];
        $qualifiedName = $baseQualifiedName;
        $suffix = 2;
        while (isset($seenCallables[$entry['source_id'] . '::' . $qualifiedName])) {
            $qualifiedName = $baseQualifiedName . '#' . $suffix;
            $suffix++;
        }
        $entry['qualified_name'] = $qualifiedName;
        $entry['id'] = $entry['source_id'] . '::' . $qualifiedName;
        $seenCallables[$entry['id']] = true;
        $callables[] = $entry;
        $callableRanges[spl_object_id($node)] = [
            'id' => $entry['id'],
            'ownerName' => $entry['owner_name'],
            'node' => $node,
        ];
    };

    walk_nodes($nodes, function (Node $node, array $parents) use (
        $sourceId,
        &$values,
        $addCallable
    ): void {
        if ($node instanceof Expr\Assign && $node->var instanceof Expr\Variable && is_string($node->var->name)) {
            $parameters = $node->expr instanceof Expr\Closure || $node->expr instanceof Expr\ArrowFunction
                ? parameter_definitions($node->expr->params)
                : [];
            $values[] = source_value_entry(
                $node->var->name,
                'private',
                $node,
                'assignment',
                value_kind($node->expr),
                $parameters
            );
        }

        if ($node instanceof Stmt\Const_) {
            foreach ($node->consts as $const) {
                $values[] = source_value_entry(
                    $const->name->toString(),
                    'public',
                    $const,
                    'constant',
                    value_kind($const->value)
                );
            }
        }

        if ($node instanceof Stmt\ClassConst) {
            foreach ($node->consts as $const) {
                $values[] = source_value_entry(
                    $const->name->toString(),
                    member_visibility($node),
                    $const,
                    'constant',
                    value_kind($const->value)
                );
            }
        }

        if ($node instanceof Stmt\Function_) {
            $name = node_name($node->name);
            $addCallable(source_callable_entry(
                $sourceId,
                $name,
                $name,
                '',
                'function',
                'public',
                $node,
                parameter_definitions($node->params),
                $node->returnType instanceof Node ? node_name($node->returnType) : ''
            ), $node);
            return;
        }

        if ($node instanceof Stmt\ClassMethod && !$node->isAbstract()) {
            $class = nearest_parent($parents, Stmt\Class_::class);
            $ownerName = $class instanceof Stmt\Class_ && $class->name !== null ? node_name($class->name) : '';
            $name = node_name($node->name);
            $kind = $name === '__construct' ? 'constructor' : ($node->isStatic() ? 'staticmethod' : 'method');
            $addCallable(source_callable_entry(
                $sourceId,
                $name,
                $ownerName !== '' ? $ownerName . '.' . $name : $name,
                $ownerName,
                $kind,
                member_visibility($node),
                $node,
                parameter_definitions($node->params),
                $node->returnType instanceof Node ? node_name($node->returnType) : ''
            ), $node);
            return;
        }

        if ($node instanceof Expr\Closure || $node instanceof Expr\ArrowFunction) {
            [$name, $qualifiedName, $ownerName, $visibility, $startNode] = callable_name_for_expr($node, $parents);
            $addCallable(source_callable_entry(
                $sourceId,
                $name,
                $qualifiedName,
                $ownerName,
                str_starts_with($name, '<anonymous>@') ? 'anonymous' : 'callable_value',
                $visibility,
                $startNode,
                parameter_definitions($node->params),
                $node->returnType instanceof Node ? node_name($node->returnType) : ''
            ), $node);
        }
    });

    return [
        'values' => $values,
        'callables' => $callables,
        'callable_ranges' => $callableRanges,
    ];
}

function collect_calls(array $nodes, string $sourceId, array $callables, array $callableRanges): array {
    $calls = [];
    $byName = [];
    $byQualifiedName = [];
    $constructorsByName = [];

    foreach ($callables as $callable) {
        $byQualifiedName[$callable['qualified_name']] = $callable['id'];
        if (in_array($callable['kind'], ['function', 'callable_value'], true)) {
            $byName[$callable['name']] = $callable['id'];
        }
        if ($callable['kind'] === 'constructor' && $callable['owner_name'] !== '') {
            $constructorsByName[$callable['owner_name']] = $callable['id'];
        }
    }

    walk_nodes($nodes, function (Node $node, array $parents) use (
        &$calls,
        $sourceId,
        $callableRanges,
        $byName,
        $byQualifiedName,
        $constructorsByName
    ): void {
        $expression = '';
        $isConstructor = false;
        if ($node instanceof Expr\FuncCall) {
            $expression = expr_name($node->name);
        } elseif ($node instanceof Expr\MethodCall) {
            $expression = expr_name($node);
        } elseif ($node instanceof Expr\StaticCall) {
            $expression = expr_name($node);
        } elseif ($node instanceof Expr\New_) {
            $expression = expr_name($node->class);
            $isConstructor = true;
        } else {
            return;
        }

        $owner = function_parent($parents);
        if ($owner === null) {
            return;
        }
        $range = $callableRanges[spl_object_id($owner)] ?? null;
        if ($range === null || $expression === '') {
            return;
        }

        $targetCallableId = '';
        $resolution = 'unresolved';
        if ($isConstructor && isset($constructorsByName[$expression])) {
            $targetCallableId = $constructorsByName[$expression];
            $resolution = 'resolved';
        } elseif (isset($byQualifiedName[$expression])) {
            $targetCallableId = $byQualifiedName[$expression];
            $resolution = 'resolved';
        } elseif (str_starts_with($expression, '$this->') && $range['ownerName'] !== '') {
            $qualifiedName = $range['ownerName'] . '.' . substr($expression, strlen('$this->'));
            if (isset($byQualifiedName[$qualifiedName])) {
                $targetCallableId = $byQualifiedName[$qualifiedName];
                $resolution = 'resolved';
            }
        } elseif (isset($byName[$expression])) {
            $targetCallableId = $byName[$expression];
            $resolution = 'resolved';
        }

        $calls[] = [
            'source_callable_id' => $range['id'],
            'target_callable_id' => $targetCallableId,
            'source_id' => $sourceId,
            'line' => $node->getStartLine(),
            'expression' => $expression,
            'resolution' => $resolution,
            'target_name' => expression_target_name($expression),
        ];
    });

    return $calls;
}

function extract_file(string $path, ?string $sourceId = null, ?string $sourcesRoot = null): array {
    $content = file_get_contents($path);
    if ($content === false) {
        fwrite(STDERR, "Unable to read PHP file: {$path}\n");
        exit(1);
    }

    try {
        $nodes = (new ParserFactory())->createForHostVersion()->parse($content) ?? [];
    } catch (Error $error) {
        fwrite(STDERR, $error->getMessage() . "\n");
        exit(1);
    }

    $root = $sourcesRoot ?? dirname($path);
    $resolvedSourceId = $sourceId ?? source_id_for_path($path, $root);
    $definitions = collect_definitions($nodes, $resolvedSourceId);
    $graph = collect_values_and_callables($nodes, $resolvedSourceId);

    return [
        'imports' => collect_imports($nodes),
        'exports' => $definitions['exports'],
        'classes' => $definitions['classes'],
        'interfaces' => $definitions['interfaces'],
        'types' => $definitions['types'],
        'abstract_classes' => $definitions['abstract_classes'],
        'functions' => $definitions['functions'],
        'values' => $graph['values'],
        'callables' => $graph['callables'],
        'calls' => collect_calls($nodes, $resolvedSourceId, $graph['callables'], $graph['callable_ranges']),
        'line_count' => line_count_for_content($content),
        'code_line_count' => code_line_count_for_content($content),
        'public_symbol_count' => count($definitions['exports']),
    ];
}

function extract_batch_from_stdin(string $sourcesRoot): array {
    $pathsBySourceId = json_decode(stream_get_contents(STDIN), true);
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
    $pathsBySourceId = json_decode(stream_get_contents(STDIN), true);
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
