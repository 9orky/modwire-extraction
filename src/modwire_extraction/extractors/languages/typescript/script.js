#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

function buildLineStarts(content) {
    const lineStarts = [0];
    for (let index = 0; index < content.length; index += 1) {
        if (content[index] === '\n') {
            lineStarts.push(index + 1);
        }
    }
    return lineStarts;
}

function lineNumberAt(lineStarts, index) {
    let low = 0;
    let high = lineStarts.length - 1;
    while (low <= high) {
        const middle = Math.floor((low + high) / 2);
        if (lineStarts[middle] <= index) {
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    return high + 1;
}

function lineSpan(lineStarts, startIndex, endIndex) {
    return lineNumberAt(lineStarts, endIndex) - lineNumberAt(lineStarts, startIndex) + 1;
}

function findMatchingBrace(content, openBraceIndex) {
    let depth = 0;
    let inSingleQuote = false;
    let inDoubleQuote = false;
    let inTemplate = false;
    let inLineComment = false;
    let inBlockComment = false;

    for (let index = openBraceIndex; index < content.length; index += 1) {
        const current = content[index];
        const next = content[index + 1];

        if (inLineComment) {
            if (current === '\n') {
                inLineComment = false;
            }
            continue;
        }
        if (inBlockComment) {
            if (current === '*' && next === '/') {
                inBlockComment = false;
                index += 1;
            }
            continue;
        }
        if (inSingleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '\'') {
                inSingleQuote = false;
            }
            continue;
        }
        if (inDoubleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '"') {
                inDoubleQuote = false;
            }
            continue;
        }
        if (inTemplate) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '`') {
                inTemplate = false;
            }
            continue;
        }

        if (current === '/' && next === '/') {
            inLineComment = true;
            index += 1;
            continue;
        }
        if (current === '/' && next === '*') {
            inBlockComment = true;
            index += 1;
            continue;
        }
        if (current === '\'') {
            inSingleQuote = true;
            continue;
        }
        if (current === '"') {
            inDoubleQuote = true;
            continue;
        }
        if (current === '`') {
            inTemplate = true;
            continue;
        }
        if (current === '{') {
            depth += 1;
            continue;
        }
        if (current === '}') {
            depth -= 1;
            if (depth === 0) {
                return index;
            }
        }
    }
    return openBraceIndex;
}

function findMatchingParen(content, openParenIndex) {
    let depth = 0;
    let inSingleQuote = false;
    let inDoubleQuote = false;
    let inTemplate = false;
    let inLineComment = false;
    let inBlockComment = false;

    for (let index = openParenIndex; index < content.length; index += 1) {
        const current = content[index];
        const next = content[index + 1];

        if (inLineComment) {
            if (current === '\n') {
                inLineComment = false;
            }
            continue;
        }
        if (inBlockComment) {
            if (current === '*' && next === '/') {
                inBlockComment = false;
                index += 1;
            }
            continue;
        }
        if (inSingleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '\'') {
                inSingleQuote = false;
            }
            continue;
        }
        if (inDoubleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '"') {
                inDoubleQuote = false;
            }
            continue;
        }
        if (inTemplate) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '`') {
                inTemplate = false;
            }
            continue;
        }

        if (current === '/' && next === '/') {
            inLineComment = true;
            index += 1;
            continue;
        }
        if (current === '/' && next === '*') {
            inBlockComment = true;
            index += 1;
            continue;
        }
        if (current === '\'') {
            inSingleQuote = true;
            continue;
        }
        if (current === '"') {
            inDoubleQuote = true;
            continue;
        }
        if (current === '`') {
            inTemplate = true;
            continue;
        }
        if (current === '(') {
            depth += 1;
            continue;
        }
        if (current === ')') {
            depth -= 1;
            if (depth === 0) {
                return index;
            }
        }
    }
    return openParenIndex;
}

function splitTopLevelParameters(parameterText) {
    const parameters = [];
    let startIndex = 0;
    let depth = 0;
    let inSingleQuote = false;
    let inDoubleQuote = false;
    let inTemplate = false;

    for (let index = 0; index < parameterText.length; index += 1) {
        const current = parameterText[index];

        if (inSingleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '\'') {
                inSingleQuote = false;
            }
            continue;
        }
        if (inDoubleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '"') {
                inDoubleQuote = false;
            }
            continue;
        }
        if (inTemplate) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '`') {
                inTemplate = false;
            }
            continue;
        }

        if (current === '\'') {
            inSingleQuote = true;
            continue;
        }
        if (current === '"') {
            inDoubleQuote = true;
            continue;
        }
        if (current === '`') {
            inTemplate = true;
            continue;
        }
        if ('({[<'.includes(current)) {
            depth += 1;
            continue;
        }
        if (')}]>'.includes(current)) {
            depth = Math.max(0, depth - 1);
            continue;
        }
        if (current === ',' && depth === 0) {
            parameters.push(parameterText.slice(startIndex, index).trim());
            startIndex = index + 1;
        }
    }

    parameters.push(parameterText.slice(startIndex).trim());
    return parameters.filter(Boolean);
}

function hasTopLevelCharacter(value, character) {
    let depth = 0;
    for (let index = 0; index < value.length; index += 1) {
        const current = value[index];
        if ('({[<'.includes(current)) {
            depth += 1;
            continue;
        }
        if (')}]>'.includes(current)) {
            depth = Math.max(0, depth - 1);
            continue;
        }
        if (current === character && depth === 0) {
            return true;
        }
    }
    return false;
}

function parameterCounts(parameterText) {
    const parameters = splitTopLevelParameters(parameterText);
    return {
        declared_args: parameters.length,
        optional_args: parameters.filter(parameter => {
            const withoutModifiers = parameter
                .replace(/^(?:(?:public|protected|private|readonly|override|static)\s+)*/g, '')
                .trim();
            return withoutModifiers.startsWith('...')
                || hasTopLevelCharacter(withoutModifiers, '=')
                || /^[A-Za-z_$][\w$]*\?(\s*[:=]|$)/.test(withoutModifiers);
        }).length,
    };
}

function parameterCountsFromParen(content, openParenIndex) {
    const closeParenIndex = findMatchingParen(content, openParenIndex);
    return parameterCounts(content.slice(openParenIndex + 1, closeParenIndex));
}

function parameterPropertiesFromParen(content, openParenIndex) {
    const closeParenIndex = findMatchingParen(content, openParenIndex);
    return splitTopLevelParameters(content.slice(openParenIndex + 1, closeParenIndex))
        .map(parameter => parameterProperty(parameter))
        .filter(property => property !== null);
}

function parameterProperty(parameter) {
    const withoutDecorators = parameter.replace(/^@\w+(?:\([^)]*\))?\s*/g, '').trim();
    const match = withoutDecorators.match(/^(?:(?:public|protected|private|readonly|override)\s+)+(?:\.\.\.\s*)?([A-Za-z_$][\w$]*)(\?)?/);
    if (match === null) {
        return null;
    }
    return {
        name: match[1],
        is_optional: Boolean(match[2]) || propertyTextIsOptional(withoutDecorators),
    };
}

function propertyTextIsOptional(value) {
    const typeMatch = value.match(/:\s*([^=;]+)/);
    const initializerMatch = value.match(/=\s*([^;]+)/);
    return Boolean(typeMatch && /\b(null|undefined)\b/.test(typeMatch[1]))
        || Boolean(initializerMatch && /^(null|undefined)\b/.test(initializerMatch[1].trim()));
}

function addProperty(properties, name, isOptional) {
    const existing = properties.get(name);
    properties.set(name, Boolean(existing) || isOptional);
}

function collectSignaturesFromText(value, lineStarts, baseIndex) {
    const signatures = [];

    function addSignature(kind, matchIndex, matchText, parameterText) {
        const counts = kind === 'index'
            ? { declared_args: 1, optional_args: 0 }
            : parameterCounts(parameterText);
        signatures.push({
            kind,
            line_count: lineSpan(
                lineStarts,
                baseIndex + matchIndex,
                baseIndex + matchIndex + matchText.length,
            ),
            declared_args: counts.declared_args,
            optional_args: counts.optional_args,
        });
    }

    let match;
    const constructRegex = /(?:^|\n|;)\s*new\s*\(([^)]*)\)\s*:/g;
    while ((match = constructRegex.exec(value)) !== null) {
        addSignature('construct', match.index, match[0], match[1]);
    }

    const callRegex = /(?:^|\n|;)\s*\(([^)]*)\)\s*:/g;
    while ((match = callRegex.exec(value)) !== null) {
        addSignature('call', match.index, match[0], match[1]);
    }

    const indexRegex = /(?:^|\n|;)\s*\[[^\]]+\]\s*:/g;
    while ((match = indexRegex.exec(value)) !== null) {
        addSignature('index', match.index, match[0], '');
    }

    return signatures;
}

function isWithinRanges(index, ranges) {
    return ranges.some(range => index >= range.start && index <= range.end);
}

function codeLineCount(content) {
    return content
        .split('\n')
        .filter(line => {
            const trimmed = line.trim();
            return trimmed && !trimmed.startsWith('//') && !trimmed.startsWith('/*') && !trimmed.startsWith('*');
        })
        .length;
}

function withoutExtension(value) {
    return value.replace(/\.[cm]?[jt]sx?$/, '');
}

function normalizedImportPath(importPath, isRelative, filePath, sourcesRoot) {
    if (!isRelative) {
        return importPath.replace(/^\/+|\/+$/g, '');
    }

    const absolutePath = path.resolve(path.dirname(filePath), importPath);
    return withoutExtension(path.relative(sourcesRoot, absolutePath).split(path.sep).join('/'));
}

function importedSymbol(name, alias, options) {
    return {
        name,
        alias,
        is_aliased: Boolean(alias) && alias !== name,
        is_default: options.isDefault,
        is_namespace: options.isNamespace,
        is_star: options.isStar,
    };
}

function parseNamedSymbols(specifierText) {
    return specifierText
        .split(',')
        .map(part => part.trim().replace(/^type\s+/, ''))
        .filter(Boolean)
        .map(part => {
            const match = part.match(/^([A-Za-z_$][\w$]*|default)\s+as\s+([A-Za-z_$][\w$]*)$/);
            if (match !== null) {
            return importedSymbol(match[1], match[2], {
                isDefault: false,
                isNamespace: false,
                isStar: false,
            });
        }
        return importedSymbol(part, '', {
            isDefault: false,
            isNamespace: false,
            isStar: false,
        });
    });
}

function importSymbols(importSpecifiers) {
    const specifiers = importSpecifiers.trim().replace(/^type\s+/, '');
    if (!specifiers) {
        return [];
    }

    const namespaceMatch = specifiers.match(/^\*\s+as\s+([A-Za-z_$][\w$]*)$/);
    if (namespaceMatch !== null) {
        return [importedSymbol('*', namespaceMatch[1], {
            isDefault: false,
            isNamespace: true,
            isStar: false,
        })];
    }

    const symbols = [];
    const namedMatch = specifiers.match(/\{([\s\S]*?)\}/);
    const beforeNamed = namedMatch === null
        ? specifiers
        : specifiers.slice(0, namedMatch.index).replace(/,\s*$/, '').trim();
    if (beforeNamed) {
        symbols.push(importedSymbol('default', beforeNamed, {
            isDefault: true,
            isNamespace: false,
            isStar: false,
        }));
    }
    if (namedMatch !== null) {
        symbols.push(...parseNamedSymbols(namedMatch[1]));
    }
    return symbols;
}

function collectImports(content, filePath, sourcesRoot) {
    const imports = [];
    let statementId = 0;

    function addImport(
        importPath,
        crossingType = 'module',
        isAliased = false,
        joinable = false,
        importedSymbols = [],
    ) {
        const isRelative = importPath.startsWith('.');
        const normalizedPath = normalizedImportPath(
            importPath,
            isRelative,
            filePath,
            sourcesRoot,
        );
        statementId += 1;
        imports.push({
            path: importPath,
            is_relative: isRelative,
            normalized_path: normalizedPath,
            imported_name: '',
            is_aliased: isAliased,
            crossing_type: crossingType,
            file_barrier_crossed: true,
            statement_id: statementId,
            join_key: joinable ? normalizedPath : '',
            uses_joined_import: joinable,
            imported_symbols: importedSymbols,
        });
    }

    function hasAliasedImport(importSpecifiers) {
        const specifiers = importSpecifiers.trim().replace(/^type\s+/, '');
        if (!specifiers) {
            return false;
        }
        if (/\*\s+as\s+[$\w]+/.test(specifiers)) {
            return true;
        }

        const namedImport = specifiers.match(/\{([\s\S]*?)\}/);
        return namedImport !== null && /\bas\b/.test(namedImport[1]);
    }

    let match;
    const importRegex = /import\s+([\s\S]*?)\s+from\s+['"](.*?)['"]/g;
    while ((match = importRegex.exec(content)) !== null) {
        const importSpecifiers = match[1].trim().replace(/^type\s+/, '');
        const isNamespaceImport = importSpecifiers.startsWith('*');
        addImport(
            match[2],
            Boolean(importSpecifiers) && !isNamespaceImport
                ? 'symbol'
                : 'module',
            hasAliasedImport(importSpecifiers),
            !isNamespaceImport,
            importSymbols(importSpecifiers),
        );
    }

    const sideEffectImportRegex = /import\s+['"](.*?)['"]/g;
    while ((match = sideEffectImportRegex.exec(content)) !== null) {
        addImport(match[1]);
    }

    const dynamicImportRegex = /import\(['"](.*?)['"]\)/g;
    while ((match = dynamicImportRegex.exec(content)) !== null) {
        addImport(match[1]);
    }

    const requireRegex = /require\(['"](.*?)['"]\)/g;
    while ((match = requireRegex.exec(content)) !== null) {
        addImport(match[1]);
    }

    return imports;
}

function collectClasses(content, lineStarts) {
    const classes = [];
    const classRanges = [];
    const classRegex = /\b(export\s+(?:default\s+)?)?class\s+([A-Za-z_$][\w$]*)[^{]*\{/g;
    let match;

    while ((match = classRegex.exec(content)) !== null) {
        if (/\babstract\s+$/.test(content.slice(Math.max(0, match.index - 32), match.index))) {
            continue;
        }
        const openBraceIndex = content.indexOf('{', match.index);
        const closeBraceIndex = findMatchingBrace(content, openBraceIndex);
        const body = content.slice(openBraceIndex + 1, closeBraceIndex);
        const methods = [];
        const methodRanges = [];
        const properties = new Map();
        const seenMethods = new Set();
        const methodRegex = /(?:^|\n)\s*((?:public|protected|private|static|async|get|set|readonly|override)\s+)*([#A-Za-z_$][\w$]*)\s*\(/g;
        let methodMatch;

        while ((methodMatch = methodRegex.exec(body)) !== null) {
            const methodName = methodMatch[2];
            if (seenMethods.has(methodName)) {
                continue;
            }
            seenMethods.add(methodName);
            const methodStart = openBraceIndex + 1 + methodMatch.index;
            const methodOpenParen = body.indexOf('(', methodMatch.index);
            const methodCloseParen = findMatchingParen(body, methodOpenParen);
            const methodOpenBrace = body.indexOf('{', methodCloseParen);
            if (methodOpenBrace === -1) {
                continue;
            }
            const methodBraceIndex = openBraceIndex + 1 + methodOpenBrace;
            const methodCloseBraceIndex = findMatchingBrace(content, methodBraceIndex);
            methodRanges.push({
                start: methodMatch.index,
                end: methodCloseBraceIndex - openBraceIndex - 1,
            });
            const counts = parameterCountsFromParen(
                body,
                methodOpenParen,
            );
            const methodVisibility = methodVisibilityFromTokens(
                methodMatch[1] || '',
                methodName,
            );
            methods.push({
                name: methodName,
                visibility: methodVisibility,
                visibility_intent: visibilityIntent(methodName, methodVisibility),
                line_count: lineSpan(lineStarts, methodStart, methodCloseBraceIndex),
                declared_args: counts.declared_args,
                optional_args: counts.optional_args,
            });
            if (methodName === 'constructor') {
                for (const property of parameterPropertiesFromParen(body, methodOpenParen)) {
                    addProperty(properties, property.name, property.is_optional);
                }
            }
        }

        const propertyRegex = /(?:^|\n)\s*(?:(?:public|protected|private|static|readonly|declare|override|abstract|accessor)\s+)*([#A-Za-z_$][\w$]*)(\?)?\s*(?:(?::([^;=\n{]+))|(?:=\s*([^;\n]+))|;)/g;
        let propertyMatch;
        while ((propertyMatch = propertyRegex.exec(body)) !== null) {
            if (isWithinRanges(propertyMatch.index, methodRanges)) {
                continue;
            }
            addProperty(
                properties,
                propertyMatch[1],
                Boolean(propertyMatch[2]) || propertyTextIsOptional(propertyMatch[0]),
            );
        }
        classes.push({
            name: match[2],
            visibility: match[1] ? 'public' : 'private',
            visibility_intent: visibilityIntent(match[2], match[1] ? 'public' : 'private'),
            methods,
            properties: Array.from(properties, ([name, is_optional]) => ({
                name,
                is_optional,
            })),
            line_count: lineSpan(lineStarts, match.index, closeBraceIndex),
        });
        classRanges.push({ start: match.index, end: closeBraceIndex });
    }

    return { classes, classRanges };
}

function collectInterfaces(content, lineStarts) {
    const interfaces = [];
    const interfaceRegex = /\b(export\s+)?interface\s+([A-Za-z_$][\w$]*)([^{]*)\{/g;
    let match;

    while ((match = interfaceRegex.exec(content)) !== null) {
        const openBraceIndex = content.indexOf('{', match.index);
        const closeBraceIndex = findMatchingBrace(content, openBraceIndex);
        const body = content.slice(openBraceIndex + 1, closeBraceIndex);
        const methods = [];
        const properties = new Map();
        const signatures = collectSignaturesFromText(
            body,
            lineStarts,
            openBraceIndex + 1,
        );

        const methodRegex = /(?:^|\n)\s*([A-Za-z_$][\w$]*)\??\s*\(([^)]*)\)/g;
        let methodMatch;
        while ((methodMatch = methodRegex.exec(body)) !== null) {
            const methodName = methodMatch[1];
            if (methodName === 'new') {
                continue;
            }
            const openParenIndex = body.indexOf('(', methodMatch.index);
            const closeParenIndex = findMatchingParen(body, openParenIndex);
            const counts = parameterCountsFromParen(body, openParenIndex);
            methods.push({
                name: methodName,
                visibility: 'public',
                visibility_intent: visibilityIntent(methodName, 'public'),
                line_count: lineSpan(
                    lineStarts,
                    openBraceIndex + 1 + methodMatch.index,
                    openBraceIndex + 1 + closeParenIndex,
                ),
                declared_args: counts.declared_args,
                optional_args: counts.optional_args,
            });
        }

        const propertyRegex = /(?:^|\n)\s*(?:(?:readonly)\s+)*([A-Za-z_$][\w$]*)(\?)?\s*:\s*([^;\n]+)/g;
        let propertyMatch;
        while ((propertyMatch = propertyRegex.exec(body)) !== null) {
            const propertyName = propertyMatch[1];
            addProperty(
                properties,
                propertyName,
                Boolean(propertyMatch[2]) || propertyTextIsOptional(propertyMatch[0]),
            );
        }

        interfaces.push({
            name: match[2],
            visibility: match[1] ? 'public' : 'private',
            visibility_intent: visibilityIntent(match[2], match[1] ? 'public' : 'private'),
            methods,
            properties: Array.from(properties, ([name, is_optional]) => ({
                name,
                is_optional,
            })),
            signatures,
            line_count: lineSpan(lineStarts, match.index, closeBraceIndex),
        });
    }

    return interfaces;
}

function findTopLevelSemicolon(content, startIndex) {
    let depth = 0;
    let inSingleQuote = false;
    let inDoubleQuote = false;
    let inTemplate = false;
    let inLineComment = false;
    let inBlockComment = false;

    for (let index = startIndex; index < content.length; index += 1) {
        const current = content[index];
        const next = content[index + 1];

        if (inLineComment) {
            if (current === '\n') {
                inLineComment = false;
            }
            continue;
        }
        if (inBlockComment) {
            if (current === '*' && next === '/') {
                inBlockComment = false;
                index += 1;
            }
            continue;
        }
        if (inSingleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '\'') {
                inSingleQuote = false;
            }
            continue;
        }
        if (inDoubleQuote) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '"') {
                inDoubleQuote = false;
            }
            continue;
        }
        if (inTemplate) {
            if (current === '\\') {
                index += 1;
                continue;
            }
            if (current === '`') {
                inTemplate = false;
            }
            continue;
        }

        if (current === '/' && next === '/') {
            inLineComment = true;
            index += 1;
            continue;
        }
        if (current === '/' && next === '*') {
            inBlockComment = true;
            index += 1;
            continue;
        }
        if (current === '\'') {
            inSingleQuote = true;
            continue;
        }
        if (current === '"') {
            inDoubleQuote = true;
            continue;
        }
        if (current === '`') {
            inTemplate = true;
            continue;
        }
        if ('({[<'.includes(current)) {
            depth += 1;
            continue;
        }
        if (')}]>'.includes(current)) {
            depth = Math.max(0, depth - 1);
            continue;
        }
        if (current === ';' && depth === 0) {
            return index;
        }
    }
    return content.length - 1;
}

function collectTypes(content, lineStarts) {
    const types = [];
    const typeRegex = /\b(export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=/g;
    let match;

    while ((match = typeRegex.exec(content)) !== null) {
        const valueStartIndex = typeRegex.lastIndex;
        const endIndex = findTopLevelSemicolon(content, valueStartIndex);
        const value = content.slice(valueStartIndex, endIndex);
        const properties = new Map();
        const signatures = collectSignaturesFromText(value, lineStarts, valueStartIndex);
        const openBraceIndex = value.indexOf('{');

        if (openBraceIndex !== -1) {
            const closeBraceIndex = findMatchingBrace(value, openBraceIndex);
            const body = value.slice(openBraceIndex + 1, closeBraceIndex);
            const propertyRegex = /(?:^|\n|;)\s*(?:(?:readonly)\s+)*([A-Za-z_$][\w$]*)(\?)?\s*:\s*([^;\n]+)/g;
            let propertyMatch;
            while ((propertyMatch = propertyRegex.exec(body)) !== null) {
                const propertyName = propertyMatch[1];
                addProperty(
                    properties,
                    propertyName,
                    Boolean(propertyMatch[2]) || propertyTextIsOptional(propertyMatch[0]),
                );
            }
        }

        types.push({
            name: match[2],
            visibility: match[1] ? 'public' : 'private',
            visibility_intent: visibilityIntent(match[2], match[1] ? 'public' : 'private'),
            properties: Array.from(properties, ([name, is_optional]) => ({
                name,
                is_optional,
            })),
            signatures,
            line_count: lineSpan(lineStarts, match.index, endIndex),
        });
    }

    return types;
}

function collectAbstractClasses(content, lineStarts) {
    const abstractClasses = [];
    const classRegex = /\b(export\s+(?:default\s+)?)?abstract\s+class\s+([A-Za-z_$][\w$]*)[^{]*\{/g;
    let match;

    while ((match = classRegex.exec(content)) !== null) {
        const openBraceIndex = content.indexOf('{', match.index);
        const closeBraceIndex = findMatchingBrace(content, openBraceIndex);
        const body = content.slice(openBraceIndex + 1, closeBraceIndex);
        const abstractMethods = [];
        const concreteMethods = [];
        const methodRanges = [];
        const properties = new Map();
        const seenMethods = new Set();
        const methodRegex = /(?:^|\n)\s*((?:public|protected|private|static|async|get|set|readonly|override|abstract)\s+)*([#A-Za-z_$][\w$]*)\s*\(/g;
        let methodMatch;

        while ((methodMatch = methodRegex.exec(body)) !== null) {
            const methodName = methodMatch[2];
            if (seenMethods.has(methodName)) {
                continue;
            }
            seenMethods.add(methodName);
            const methodStart = openBraceIndex + 1 + methodMatch.index;
            const methodOpenParen = body.indexOf('(', methodMatch.index);
            const methodCloseParen = findMatchingParen(body, methodOpenParen);
            const methodOpenBrace = body.indexOf('{', methodCloseParen);
            const methodSemicolon = body.indexOf(';', methodCloseParen);
            const isAbstract = /\babstract\b/.test(methodMatch[1] || '')
                || methodOpenBrace === -1
                || (methodSemicolon !== -1 && methodSemicolon < methodOpenBrace);
            const methodEnd = isAbstract
                ? (methodSemicolon === -1 ? methodCloseParen : methodSemicolon)
                : findMatchingBrace(content, openBraceIndex + 1 + methodOpenBrace);
            methodRanges.push({
                start: methodMatch.index,
                end: methodEnd - openBraceIndex - 1,
            });
            const counts = parameterCountsFromParen(body, methodOpenParen);
            const methodVisibility = methodVisibilityFromTokens(
                methodMatch[1] || '',
                methodName,
            );
            const method = {
                name: methodName,
                visibility: methodVisibility,
                visibility_intent: visibilityIntent(methodName, methodVisibility),
                line_count: lineSpan(lineStarts, methodStart, methodEnd),
                declared_args: counts.declared_args,
                optional_args: counts.optional_args,
            };
            if (isAbstract) {
                abstractMethods.push(method);
            } else {
                concreteMethods.push(method);
            }
            if (methodName === 'constructor') {
                for (const property of parameterPropertiesFromParen(body, methodOpenParen)) {
                    addProperty(properties, property.name, property.is_optional);
                }
            }
        }

        const propertyRegex = /(?:^|\n)\s*(?:(?:public|protected|private|static|readonly|declare|override|abstract|accessor)\s+)*([#A-Za-z_$][\w$]*)(\?)?\s*(?:(?::([^;=\n{]+))|(?:=\s*([^;\n]+))|;)/g;
        let propertyMatch;
        while ((propertyMatch = propertyRegex.exec(body)) !== null) {
            if (isWithinRanges(propertyMatch.index, methodRanges)) {
                continue;
            }
            addProperty(
                properties,
                propertyMatch[1],
                Boolean(propertyMatch[2]) || propertyTextIsOptional(propertyMatch[0]),
            );
        }
        abstractClasses.push({
            name: match[2],
            visibility: match[1] ? 'public' : 'private',
            visibility_intent: visibilityIntent(match[2], match[1] ? 'public' : 'private'),
            abstract_methods: abstractMethods,
            concrete_methods: concreteMethods,
            properties: Array.from(properties, ([name, is_optional]) => ({
                name,
                is_optional,
            })),
            line_count: lineSpan(lineStarts, match.index, closeBraceIndex),
        });
    }

    return abstractClasses;
}

function collectFunctions(content, lineStarts, classRanges) {
    const functions = [];
    const seenNames = new Set();

    function addFunction(name, startIndex, endIndex, counts, visibility) {
        if (!name || seenNames.has(name) || isWithinRanges(startIndex, classRanges)) {
            return;
        }
        seenNames.add(name);
        functions.push({
            name,
            visibility,
            visibility_intent: visibilityIntent(name, visibility),
            line_count: lineSpan(lineStarts, startIndex, endIndex),
            declared_args: counts.declared_args,
            optional_args: counts.optional_args,
        });
    }

    let match;
    const functionRegex = /\b(export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/g;
    while ((match = functionRegex.exec(content)) !== null) {
        const openParenIndex = content.indexOf('(', match.index);
        const closeParenIndex = findMatchingParen(content, openParenIndex);
        const openBraceIndex = content.indexOf('{', closeParenIndex);
        if (openBraceIndex === -1) {
            continue;
        }
        addFunction(
            match[2],
            match.index,
            findMatchingBrace(content, openBraceIndex),
            parameterCountsFromParen(content, openParenIndex),
            match[1] ? 'public' : 'private',
        );
    }

    const arrowFunctionRegex = /\b(export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*(\{)?/g;
    while ((match = arrowFunctionRegex.exec(content)) !== null) {
        const hasBlockBody = match[4] === '{';
        const openBraceIndex = hasBlockBody ? content.indexOf('{', match.index) : match.index;
        const endIndex = hasBlockBody ? findMatchingBrace(content, openBraceIndex) : match.index;
        addFunction(
            match[2],
            match.index,
            endIndex,
            parameterCounts(match[3].replace(/^\(|\)$/g, '')),
            match[1] ? 'public' : 'private',
        );
    }

    return functions;
}

function methodVisibilityFromTokens(tokens, name) {
    if (name.startsWith('#')) {
        return 'private';
    }
    if (/\bprivate\b/.test(tokens)) {
        return 'private';
    }
    if (/\bprotected\b/.test(tokens)) {
        return 'protected';
    }
    return 'public';
}

function visibilityIntent(name, visibility) {
    if (name.startsWith('#') || (name.startsWith('__') && !name.endsWith('__'))) {
        return 'private';
    }
    if (name.startsWith('_') && !name.endsWith('__')) {
        return 'protected';
    }
    return visibility;
}

function sourceExport(
    name,
    kind,
    options,
) {
    const exportPath = options.path;
    const isRelative = exportPath.startsWith('.');
    return {
        name,
        local_name: options.localName,
        kind,
        crossing_type: options.crossingType,
        path: exportPath,
        is_relative: isRelative,
        normalized_path: options.normalizedPath,
        is_reexport: options.isReexport,
        is_default: options.isDefault,
        is_aliased: options.isAliased,
        statement_id: options.statementId,
    };
}

function addExport(exports, seen, sourceExportValue) {
    const key = [
        sourceExportValue.name,
        sourceExportValue.kind,
        sourceExportValue.crossing_type,
        sourceExportValue.normalized_path,
    ].join('\0');
    if (seen.has(key)) {
        return;
    }
    seen.add(key);
    exports.push(sourceExportValue);
}

function collectExports(content, filePath, sourcesRoot) {
    const exports = [];
    const seen = new Set();
    let match;
    let statementId = 0;

    function normalizedPathForExport(exportPath) {
        if (!exportPath) {
            return '';
        }
        return normalizedImportPath(
            exportPath,
            exportPath.startsWith('.'),
            filePath,
            sourcesRoot,
        );
    }

    function addDirect(name, kind, options) {
        addExport(exports, seen, sourceExport(name, kind, options));
    }

    function directExportOptions(localName, isDefault) {
        return {
            localName,
            path: '',
            normalizedPath: '',
            crossingType: 'symbol',
            isReexport: false,
            isDefault,
            isAliased: false,
            statementId: 0,
        };
    }

    const defaultClassRegex = /\bexport\s+default\s+class(?:\s+([A-Za-z_$][\w$]*))?/g;
    while ((match = defaultClassRegex.exec(content)) !== null) {
        addDirect('default', 'class', {
            ...directExportOptions(match[1] || 'default', true),
        });
    }

    const defaultFunctionRegex = /\bexport\s+default\s+(?:async\s+)?function(?:\s+([A-Za-z_$][\w$]*))?/g;
    while ((match = defaultFunctionRegex.exec(content)) !== null) {
        addDirect('default', 'function', {
            ...directExportOptions(match[1] || 'default', true),
        });
    }

    const defaultValueRegex = /\bexport\s+default\s+(?!class\b|(?:async\s+)?function\b)/g;
    while ((match = defaultValueRegex.exec(content)) !== null) {
        addDirect('default', 'value', {
            ...directExportOptions('default', true),
        });
    }

    const abstractClassRegex = /\bexport\s+abstract\s+class\s+([A-Za-z_$][\w$]*)/g;
    while ((match = abstractClassRegex.exec(content)) !== null) {
        addDirect(match[1], 'abstract_class', {
            ...directExportOptions(match[1], false),
        });
    }

    const classRegex = /\bexport\s+class\s+([A-Za-z_$][\w$]*)/g;
    while ((match = classRegex.exec(content)) !== null) {
        addDirect(match[1], 'class', {
            ...directExportOptions(match[1], false),
        });
    }

    const interfaceRegex = /\bexport\s+interface\s+([A-Za-z_$][\w$]*)/g;
    while ((match = interfaceRegex.exec(content)) !== null) {
        addDirect(match[1], 'interface', {
            ...directExportOptions(match[1], false),
        });
    }

    const typeRegex = /\bexport\s+type\s+([A-Za-z_$][\w$]*)\s*=/g;
    while ((match = typeRegex.exec(content)) !== null) {
        addDirect(match[1], 'type', {
            ...directExportOptions(match[1], false),
        });
    }

    const functionRegex = /\bexport\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g;
    while ((match = functionRegex.exec(content)) !== null) {
        addDirect(match[1], 'function', {
            ...directExportOptions(match[1], false),
        });
    }

    const valueRegex = /\bexport\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/g;
    while ((match = valueRegex.exec(content)) !== null) {
        addDirect(match[1], 'value', {
            ...directExportOptions(match[1], false),
        });
    }

    const namedReexportRegex = /\bexport\s*\{([\s\S]*?)\}\s*from\s*['"](.*?)['"]/g;
    while ((match = namedReexportRegex.exec(content)) !== null) {
        statementId += 1;
        const exportPath = match[2];
        for (const symbol of parseNamedSymbols(match[1])) {
            addExport(exports, seen, sourceExport(
                symbol.alias || symbol.name,
                'unknown',
                {
                    localName: symbol.name,
                    path: exportPath,
                    normalizedPath: normalizedPathForExport(exportPath),
                    crossingType: 'symbol',
                    isReexport: true,
                    isDefault: false,
                    isAliased: symbol.is_aliased,
                    statementId,
                },
            ));
        }
    }

    const starReexportRegex = /\bexport\s+\*\s+from\s*['"](.*?)['"]/g;
    while ((match = starReexportRegex.exec(content)) !== null) {
        statementId += 1;
        addExport(exports, seen, sourceExport('*', 'unknown', {
            localName: '*',
            crossingType: 'module',
            path: match[1],
            normalizedPath: normalizedPathForExport(match[1]),
            isReexport: true,
            isDefault: false,
            isAliased: false,
            statementId,
        }));
    }

    const localNamedExportRegex = /\bexport\s*\{([\s\S]*?)\}(?!\s*from\b)/g;
    while ((match = localNamedExportRegex.exec(content)) !== null) {
        statementId += 1;
        for (const symbol of parseNamedSymbols(match[1])) {
            addExport(exports, seen, sourceExport(
                symbol.alias || symbol.name,
                'unknown',
                {
                    localName: symbol.name,
                    path: '',
                    normalizedPath: '',
                    crossingType: 'symbol',
                    isReexport: false,
                    isDefault: false,
                    isAliased: symbol.is_aliased,
                    statementId,
                },
            ));
        }
    }

    return exports;
}

function sourceIdForPath(filePath, sourcesRoot) {
    return withoutExtension(path.relative(sourcesRoot, filePath).split(path.sep).join('/')).replace(/^\/+|\/+$/g, '');
}

function callableId(sourceId, qualifiedName) {
    return `${sourceId}::${qualifiedName}`;
}

function parameterName(parameter) {
    const cleaned = parameter
        .replace(/^(?:(?:public|protected|private|readonly|override|static)\s+)*/g, '')
        .replace(/^\.\.\.\s*/, '')
        .trim();
    const match = cleaned.match(/^([A-Za-z_$][\w$]*)/);
    return match === null ? cleaned : match[1];
}

function parameterDefinitions(parameterText) {
    return splitTopLevelParameters(parameterText).map(parameter => ({
        name: parameterName(parameter),
        annotation: '',
        kind: parameter.trim().startsWith('...') ? 'vararg' : 'positional',
        has_default: hasTopLevelCharacter(parameter, '=') || /\?(\s*[:=]|$)/.test(parameter),
    }));
}

function sourceCallable(options) {
    const parameters = options.parameters || [];
    return {
        id: callableId(options.sourceId, options.qualifiedName),
        source_id: options.sourceId,
        name: options.name,
        qualified_name: options.qualifiedName,
        owner_name: options.ownerName || '',
        kind: options.kind,
        visibility: options.visibility,
        visibility_intent: options.visibilityIntent,
        line_start: lineNumberAt(options.lineStarts, options.startIndex),
        line_end: lineNumberAt(options.lineStarts, options.endIndex),
        line_count: lineSpan(options.lineStarts, options.startIndex, options.endIndex),
        parameters,
        declared_args: parameters.length,
        optional_args: parameters.filter(parameter => parameter.has_default).length,
        return_annotation: '',
        decorators: [],
        docstring: '',
    };
}

function sourceValue(options) {
    const counts = options.counts || { declared_args: 0, optional_args: 0 };
    return {
        name: options.name,
        visibility: options.visibility,
        visibility_intent: options.visibilityIntent,
        line_count: lineSpan(options.lineStarts, options.startIndex, options.endIndex),
        declaration_kind: 'assignment',
        value_kind: options.valueKind,
        declared_args: counts.declared_args,
        optional_args: counts.optional_args,
    };
}

function initializerValueKind(content, startIndex) {
    const rest = content.slice(startIndex).trimStart();
    if (/^(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)/.test(rest)) {
        return 'callable';
    }
    if (/^['"`0-9]|^(?:true|false|null|undefined)\b/.test(rest)) {
        return 'literal';
    }
    if (/^[{[]/.test(rest) || /^new\s+/.test(rest)) {
        return 'object';
    }
    return 'unknown';
}

function collectTopLevelValuesAndCallables(content, lineStarts, classRanges, sourceId) {
    const values = [];
    const callables = [];
    const callableRanges = [];
    const valueRegex = /\b(export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*/g;
    let match;

    while ((match = valueRegex.exec(content)) !== null) {
        if (isWithinRanges(match.index, classRanges)) {
            continue;
        }
        const name = match[2];
        const visibility = match[1] ? 'public' : 'private';
        const valueStartIndex = valueRegex.lastIndex;
        const endIndex = findTopLevelSemicolon(content, valueStartIndex);
        const valueKind = initializerValueKind(content, valueStartIndex);
        let counts = { declared_args: 0, optional_args: 0 };
        let callableEndIndex = endIndex;
        let parameters = [];
        const afterEquals = content.slice(valueStartIndex, endIndex);
        const arrowMatch = afterEquals.match(/^\s*(?:async\s*)?(\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*(\{)?/);
        const functionMatch = afterEquals.match(/^\s*(?:async\s*)?function(?:\s+[A-Za-z_$][\w$]*)?\s*\(([^)]*)\)[^{]*\{/);
        if (arrowMatch !== null) {
            const parameterText = arrowMatch[1].replace(/^\(|\)$/g, '');
            counts = parameterCounts(parameterText);
            parameters = parameterDefinitions(parameterText);
            const bodyOpenIndex = content.indexOf('{', valueStartIndex + arrowMatch.index);
            callableEndIndex = arrowMatch[2] === '{' && bodyOpenIndex !== -1
                ? findMatchingBrace(content, bodyOpenIndex)
                : endIndex;
        } else if (functionMatch !== null) {
            counts = parameterCounts(functionMatch[1]);
            parameters = parameterDefinitions(functionMatch[1]);
            const bodyOpenIndex = content.indexOf('{', valueStartIndex + functionMatch.index);
            callableEndIndex = bodyOpenIndex === -1 ? endIndex : findMatchingBrace(content, bodyOpenIndex);
        }

        values.push(sourceValue({
            name,
            visibility,
            visibilityIntent: visibilityIntent(name, visibility),
            startIndex: match.index,
            endIndex,
            lineStarts,
            valueKind,
            counts,
        }));
        if (valueKind === 'callable') {
            const sourceCallableValue = sourceCallable({
                sourceId,
                name,
                qualifiedName: name,
                kind: 'callable_value',
                visibility,
                visibilityIntent: visibilityIntent(name, visibility),
                startIndex: match.index,
                endIndex: callableEndIndex,
                lineStarts,
                parameters,
            });
            callables.push(sourceCallableValue);
            callableRanges.push({
                id: sourceCallableValue.id,
                ownerName: '',
                bodyStart: valueStartIndex,
                bodyEnd: callableEndIndex,
            });
        }
    }

    return { values, callables, callableRanges };
}

function collectDeclarationCallables(content, lineStarts, classRanges, sourceId) {
    const callables = [];
    const callableRanges = [];
    let match;
    const functionRegex = /\b(export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/g;
    while ((match = functionRegex.exec(content)) !== null) {
        if (isWithinRanges(match.index, classRanges)) {
            continue;
        }
        const openParenIndex = content.indexOf('(', match.index);
        const closeParenIndex = findMatchingParen(content, openParenIndex);
        const openBraceIndex = content.indexOf('{', closeParenIndex);
        if (openBraceIndex === -1) {
            continue;
        }
        const closeBraceIndex = findMatchingBrace(content, openBraceIndex);
        const visibility = match[1] ? 'public' : 'private';
        const sourceCallableValue = sourceCallable({
            sourceId,
            name: match[2],
            qualifiedName: match[2],
            kind: 'function',
            visibility,
            visibilityIntent: visibilityIntent(match[2], visibility),
            startIndex: match.index,
            endIndex: closeBraceIndex,
            lineStarts,
            parameters: parameterDefinitions(content.slice(openParenIndex + 1, closeParenIndex)),
        });
        callables.push(sourceCallableValue);
        callableRanges.push({
            id: sourceCallableValue.id,
            ownerName: '',
            bodyStart: openBraceIndex + 1,
            bodyEnd: closeBraceIndex,
        });
    }

    const classRegex = /\b(export\s+(?:default\s+)?)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)[^{]*\{/g;
    while ((match = classRegex.exec(content)) !== null) {
        const className = match[2];
        const openBraceIndex = content.indexOf('{', match.index);
        const closeBraceIndex = findMatchingBrace(content, openBraceIndex);
        const body = content.slice(openBraceIndex + 1, closeBraceIndex);
        const methodRegex = /(?:^|\n)\s*((?:public|protected|private|static|async|get|set|readonly|override|abstract)\s+)*([#A-Za-z_$][\w$]*)\s*\(/g;
        let methodMatch;
        const seenMethods = new Set();
        while ((methodMatch = methodRegex.exec(body)) !== null) {
            const methodName = methodMatch[2];
            if (seenMethods.has(methodName)) {
                continue;
            }
            seenMethods.add(methodName);
            const methodStart = openBraceIndex + 1 + methodMatch.index;
            const methodOpenParen = body.indexOf('(', methodMatch.index);
            const methodCloseParen = findMatchingParen(body, methodOpenParen);
            const methodOpenBrace = body.indexOf('{', methodCloseParen);
            if (methodOpenBrace === -1) {
                continue;
            }
            const methodBraceIndex = openBraceIndex + 1 + methodOpenBrace;
            const methodCloseBraceIndex = findMatchingBrace(content, methodBraceIndex);
            const visibility = methodVisibilityFromTokens(methodMatch[1] || '', methodName);
            const kind = methodName === 'constructor'
                ? 'constructor'
                : (/\bstatic\b/.test(methodMatch[1] || '') ? 'staticmethod' : 'method');
            const qualifiedName = `${className}.${methodName}`;
            const sourceCallableValue = sourceCallable({
                sourceId,
                name: methodName,
                qualifiedName,
                ownerName: className,
                kind,
                visibility,
                visibilityIntent: visibilityIntent(methodName, visibility),
                startIndex: methodStart,
                endIndex: methodCloseBraceIndex,
                lineStarts,
                parameters: parameterDefinitions(body.slice(methodOpenParen + 1, methodCloseParen)),
            });
            callables.push(sourceCallableValue);
            callableRanges.push({
                id: sourceCallableValue.id,
                ownerName: className,
                bodyStart: methodBraceIndex + 1,
                bodyEnd: methodCloseBraceIndex,
            });
        }
    }

    return { callables, callableRanges };
}

function collectAnonymousCallables(content, lineStarts, sourceId, callableRanges) {
    const callables = [];
    const ranges = [];
    for (const parentRange of callableRanges) {
        const body = content.slice(parentRange.bodyStart, parentRange.bodyEnd);
        const arrowRegex = /(?:\(|,|\[)\s*(?:async\s*)?(\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*(\{)?/g;
        let match;
        while ((match = arrowRegex.exec(body)) !== null) {
            const startIndex = parentRange.bodyStart + match.index;
            const bodyOpenIndex = match[2] === '{' ? content.indexOf('{', startIndex) : -1;
            const endIndex = bodyOpenIndex === -1
                ? findTopLevelSemicolon(content, startIndex)
                : findMatchingBrace(content, bodyOpenIndex);
            const callableBody = content.slice(bodyOpenIndex === -1 ? startIndex : bodyOpenIndex + 1, endIndex);
            if (!/[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\s*\(/.test(callableBody)) {
                continue;
            }
            const line = lineNumberAt(lineStarts, startIndex);
            const column = startIndex - lineStarts[line - 1];
            const name = `<anonymous>@${line}:${column}`;
            const parentQualifiedName = parentRange.id.split('::')[1] || '';
            const sourceCallableValue = sourceCallable({
                sourceId,
                name,
                qualifiedName: `${parentQualifiedName}.${name}`,
                ownerName: parentRange.ownerName,
                kind: 'anonymous',
                visibility: 'public',
                visibilityIntent: 'public',
                startIndex,
                endIndex,
                lineStarts,
                parameters: parameterDefinitions(match[1].replace(/^\(|\)$/g, '')),
            });
            callables.push(sourceCallableValue);
            ranges.push({
                id: sourceCallableValue.id,
                ownerName: parentRange.ownerName,
                bodyStart: bodyOpenIndex === -1 ? startIndex : bodyOpenIndex + 1,
                bodyEnd: endIndex,
            });
        }
    }
    return { callables, callableRanges: ranges };
}

function collectCalls(content, lineStarts, sourceId, callableRanges, callables) {
    const byName = new Map();
    const byQualifiedName = new Map();
    const constructorsByName = new Map();
    for (const sourceCallableValue of callables) {
        byQualifiedName.set(sourceCallableValue.qualified_name, sourceCallableValue.id);
        if (['function', 'callable_value'].includes(sourceCallableValue.kind)) {
            byName.set(sourceCallableValue.name, sourceCallableValue.id);
        }
        if (sourceCallableValue.kind === 'constructor') {
            constructorsByName.set(sourceCallableValue.owner_name, sourceCallableValue.id);
        }
    }

    const calls = [];
    const callRegex = /\b(new\s+)?([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(/g;
    const ignored = new Set(['if', 'for', 'while', 'switch', 'catch', 'function', 'return']);
    for (const range of callableRanges) {
        const body = content.slice(range.bodyStart, range.bodyEnd);
        let match;
        while ((match = callRegex.exec(body)) !== null) {
            const expression = match[2];
            const targetName = expression.split('.').pop();
            if (ignored.has(expression) || ignored.has(targetName)) {
                continue;
            }
            const absoluteIndex = range.bodyStart + match.index;
            const previous = content.slice(Math.max(0, absoluteIndex - 16), absoluteIndex);
            if (/\bfunction\s+$/.test(previous)) {
                continue;
            }
            let targetCallableId = '';
            let resolution = 'unresolved';
            if (match[1] && constructorsByName.has(expression)) {
                targetCallableId = constructorsByName.get(expression);
                resolution = 'resolved';
            } else if (byQualifiedName.has(expression)) {
                targetCallableId = byQualifiedName.get(expression);
                resolution = 'resolved';
            } else if (expression.startsWith('this.') && range.ownerName) {
                const qualifiedName = `${range.ownerName}.${expression.slice('this.'.length)}`;
                if (byQualifiedName.has(qualifiedName)) {
                    targetCallableId = byQualifiedName.get(qualifiedName);
                    resolution = 'resolved';
                }
            } else if (byName.has(expression)) {
                targetCallableId = byName.get(expression);
                resolution = 'resolved';
            }
            calls.push({
                source_callable_id: range.id,
                target_callable_id: targetCallableId,
                source_id: sourceId,
                line: lineNumberAt(lineStarts, absoluteIndex),
                expression,
                resolution,
                target_name: targetName,
            });
        }
    }
    return calls;
}

function collectCallableGraph(content, lineStarts, classRanges, sourceId) {
    const valuesAndCallableValues = collectTopLevelValuesAndCallables(content, lineStarts, classRanges, sourceId);
    const declarations = collectDeclarationCallables(content, lineStarts, classRanges, sourceId);
    const callableRanges = [
        ...valuesAndCallableValues.callableRanges,
        ...declarations.callableRanges,
    ];
    const callables = [
        ...valuesAndCallableValues.callables,
        ...declarations.callables,
    ];
    const anonymous = collectAnonymousCallables(content, lineStarts, sourceId, callableRanges);
    const allCallableRanges = [...callableRanges, ...anonymous.callableRanges];
    const allCallables = [...callables, ...anonymous.callables];
    return {
        values: valuesAndCallableValues.values,
        callables: allCallables,
        calls: collectCalls(content, lineStarts, sourceId, allCallableRanges, allCallables),
    };
}

function extractFile(filePath, sourcesRoot, sourceId = null) {
    const content = fs.readFileSync(filePath, 'utf8');
    const lineStarts = buildLineStarts(content);
    const resolvedSourceId = sourceId || sourceIdForPath(filePath, sourcesRoot);
    const { classes, classRanges } = collectClasses(content, lineStarts);
    const interfaces = collectInterfaces(content, lineStarts);
    const types = collectTypes(content, lineStarts);
    const abstractClasses = collectAbstractClasses(content, lineStarts);
    const functions = collectFunctions(content, lineStarts, classRanges);
    const callableGraph = collectCallableGraph(content, lineStarts, classRanges, resolvedSourceId);

    return {
        imports: collectImports(content, filePath, sourcesRoot),
        exports: collectExports(content, filePath, sourcesRoot),
        classes,
        interfaces,
        types,
        abstract_classes: abstractClasses,
        functions,
        values: callableGraph.values,
        callables: callableGraph.callables,
        calls: callableGraph.calls,
        line_count: content.split('\n').length,
        code_line_count: codeLineCount(content),
        public_symbol_count: publicSymbolCount(content),
    };
}

function extractBatchFromStdin(sourcesRoot) {
    const pathsBySourceId = JSON.parse(fs.readFileSync(0, 'utf8'));
    if (
        pathsBySourceId === null
        || Array.isArray(pathsBySourceId)
        || typeof pathsBySourceId !== 'object'
    ) {
        console.error('Expected a JSON object mapping source ids to TypeScript file paths.');
        process.exit(1);
    }

    const result = {};
    for (const [sourceId, filePath] of Object.entries(pathsBySourceId)) {
        if (typeof sourceId !== 'string' || typeof filePath !== 'string') {
            console.error('Expected source ids and paths to be strings.');
            process.exit(1);
        }
        result[sourceId] = extractFile(path.resolve(filePath), sourcesRoot, sourceId);
    }
    return result;
}

function writeBatchJsonlFromStdin(sourcesRoot) {
    const pathsBySourceId = JSON.parse(fs.readFileSync(0, 'utf8'));
    if (
        pathsBySourceId === null
        || Array.isArray(pathsBySourceId)
        || typeof pathsBySourceId !== 'object'
    ) {
        console.error('Expected a JSON object mapping source ids to TypeScript file paths.');
        process.exit(1);
    }

    for (const [sourceId, filePath] of Object.entries(pathsBySourceId)) {
        if (typeof sourceId !== 'string' || typeof filePath !== 'string') {
            console.error('Expected source ids and paths to be strings.');
            process.exit(1);
        }
        console.log(JSON.stringify([
            sourceId,
            extractFile(path.resolve(filePath), sourcesRoot, sourceId),
        ]));
    }
}

function publicSymbolCount(content) {
    const symbols = new Set();
    let match;

    const classRegex = /\bexport\s+(?:default\s+)?class\s+([A-Za-z_$][\w$]*)/g;
    while ((match = classRegex.exec(content)) !== null) {
        symbols.add(match[1]);
    }

    const abstractClassRegex = /\bexport\s+(?:default\s+)?abstract\s+class\s+([A-Za-z_$][\w$]*)/g;
    while ((match = abstractClassRegex.exec(content)) !== null) {
        symbols.add(match[1]);
    }

    const interfaceRegex = /\bexport\s+interface\s+([A-Za-z_$][\w$]*)/g;
    while ((match = interfaceRegex.exec(content)) !== null) {
        symbols.add(match[1]);
    }

    const typeRegex = /\bexport\s+type\s+([A-Za-z_$][\w$]*)/g;
    while ((match = typeRegex.exec(content)) !== null) {
        symbols.add(match[1]);
    }

    const functionRegex = /\bexport\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g;
    while ((match = functionRegex.exec(content)) !== null) {
        symbols.add(match[1]);
    }

    const arrowFunctionRegex = /\bexport\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=/g;
    while ((match = arrowFunctionRegex.exec(content)) !== null) {
        symbols.add(match[1]);
    }

    return symbols.size;
}

if (process.argv[2] === '--batch') {
    const sourcesRoot = process.argv[3] ? path.resolve(process.argv[3]) : process.cwd();
    if (process.argv.includes('--jsonl')) {
        writeBatchJsonlFromStdin(sourcesRoot);
    } else {
        console.log(JSON.stringify(extractBatchFromStdin(sourcesRoot)));
    }
} else {
    console.log(JSON.stringify(extractFile(
        path.resolve(process.argv[2]),
        process.argv[3] ? path.resolve(process.argv[3]) : process.cwd(),
    )));
}
