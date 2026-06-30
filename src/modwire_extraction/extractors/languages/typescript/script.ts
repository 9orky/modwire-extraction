#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { Node, Project, ScriptKind, SyntaxKind, ts } from 'ts-morph';

function scriptKindForPath(filePath) {
    switch (path.extname(filePath).toLowerCase()) {
        case '.js':
            return ScriptKind.JS;
        case '.jsx':
            return ScriptKind.JSX;
        case '.tsx':
            return ScriptKind.TSX;
        default:
            return ScriptKind.TS;
    }
}

function parseSourceFile(filePath, content) {
    const project = new Project({
        compilerOptions: {
            allowJs: true,
            checkJs: false,
            jsx: ts.JsxEmit.Preserve,
            target: ts.ScriptTarget.ESNext,
        },
        skipLoadingLibFiles: true,
        useInMemoryFileSystem: true,
    });
    return project.createSourceFile(filePath, content, {
        overwrite: true,
        scriptKind: scriptKindForPath(filePath),
    });
}

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
    return lineNumberAt(lineStarts, Math.max(startIndex, endIndex)) - lineNumberAt(lineStarts, startIndex) + 1;
}

function withoutExtension(value) {
    return value.replace(/\.[^.\/\\]+$/, '');
}

function sourceIdForPath(filePath, sourcesRoot) {
    return withoutExtension(path.relative(sourcesRoot, filePath).split(path.sep).join('/')).replace(/^\/+|\/+$/g, '');
}

function normalizedImportPath(importPath, isRelative, filePath, sourcesRoot) {
    if (!isRelative) {
        return importPath;
    }
    const absolutePath = path.resolve(path.dirname(filePath), importPath);
    return withoutExtension(path.relative(sourcesRoot, absolutePath).split(path.sep).join('/')).replace(/^\/+|\/+$/g, '');
}

function moduleSpecifierValue(declaration) {
    const specifier = declaration.compilerNode.moduleSpecifier;
    if (
        specifier === undefined
        || (!ts.isStringLiteral(specifier) && !ts.isNoSubstitutionTemplateLiteral(specifier))
    ) {
        return null;
    }
    return specifier.text;
}

function endIndexForNode(node) {
    return Math.max(node.getStart(), node.getEnd() - 1);
}

function textOf(node) {
    return node === undefined ? '' : node.getText();
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

function visibilityFromModifiers(node, fallback = 'public') {
    const modifiers = typeof node.getModifiers === 'function'
        ? node.getModifiers().map(modifier => modifier.getText())
        : [];
    if (modifiers.includes('private')) {
        return 'private';
    }
    if (modifiers.includes('protected')) {
        return 'protected';
    }
    if (modifiers.includes('public')) {
        return 'public';
    }
    const name = typeof node.getName === 'function' ? node.getName() : '';
    return name.startsWith('#') ? 'private' : fallback;
}

function isExported(node) {
    return Boolean(
        (typeof node.hasExportKeyword === 'function' && node.hasExportKeyword())
        || (typeof node.isDefaultExport === 'function' && node.isDefaultExport()),
    );
}

function moduleVisibility(node) {
    return node !== undefined && isExported(node) ? 'public' : 'private';
}

function codeLineCount(content) {
    return content.split('\n').filter(line => {
        const trimmed = line.trim();
        return trimmed !== '' && !trimmed.startsWith('//');
    }).length;
}

function emptySourceFile(content) {
    return {
        imports: [],
        exports: [],
        classes: [],
        interfaces: [],
        types: [],
        abstract_classes: [],
        functions: [],
        values: [],
        callables: [],
        calls: [],
        line_count: content.split('\n').length,
        code_line_count: codeLineCount(content),
        public_symbol_count: 0,
    };
}

function shouldReturnEmptySourceFile(error) {
    if (error instanceof RangeError && error.message.includes('Maximum call stack size exceeded')) {
        return true;
    }
    return error instanceof Error && error.message.startsWith('Debug Failure');
}

function callableId(sourceId, qualifiedName) {
    return `${sourceId}::${qualifiedName}`;
}

function bindingNamesFromCompilerName(nameNode) {
    if (ts.isIdentifier(nameNode)) {
        return [nameNode.text];
    }
    if (ts.isObjectBindingPattern(nameNode) || ts.isArrayBindingPattern(nameNode)) {
        return nameNode.elements.flatMap(element => {
            if (ts.isOmittedExpression(element)) {
                return [];
            }
            return bindingNamesFromCompilerName(element.name);
        });
    }
    return [];
}

function bindingNames(nameNode) {
    return bindingNamesFromCompilerName(nameNode.compilerNode);
}

function singleBindingName(nameNode) {
    const names = bindingNames(nameNode);
    return names.length === 1 ? names[0] : '';
}

function unwrapExpression(node) {
    let current = node;
    while (
        Node.isParenthesizedExpression(current)
        || Node.isAsExpression(current)
        || Node.isSatisfiesExpression(current)
        || Node.isTypeAssertion(current)
        || Node.isNonNullExpression(current)
    ) {
        current = current.getExpression();
    }
    return current;
}

function expressionValueKind(expression) {
    if (expression === undefined) {
        return 'unknown';
    }
    const unwrapped = unwrapExpression(expression);
    if (Node.isArrowFunction(unwrapped) || Node.isFunctionExpression(unwrapped)) {
        return 'callable';
    }
    switch (unwrapped.getKind()) {
        case SyntaxKind.StringLiteral:
        case SyntaxKind.NoSubstitutionTemplateLiteral:
        case SyntaxKind.NumericLiteral:
        case SyntaxKind.BigIntLiteral:
        case SyntaxKind.TrueKeyword:
        case SyntaxKind.FalseKeyword:
        case SyntaxKind.NullKeyword:
            return 'literal';
        case SyntaxKind.ObjectLiteralExpression:
        case SyntaxKind.ArrayLiteralExpression:
        case SyntaxKind.NewExpression:
            return 'object';
        default:
            return Node.isIdentifier(unwrapped) && unwrapped.getText() === 'undefined' ? 'literal' : 'unknown';
    }
}

function parameterDefinitions(parameters) {
    return parameters.map(parameter => {
        const nameNode = parameter.getNameNode();
        const name = singleBindingName(nameNode) || nameNode.getText();
        const typeNode = typeof parameter.getTypeNode === 'function' ? parameter.getTypeNode() : undefined;
        return {
            name,
            annotation: textOf(typeNode),
            kind: parameter.isRestParameter() ? 'vararg' : 'positional',
            has_default: parameter.isRestParameter()
                || parameter.isOptional()
                || parameter.getInitializer() !== undefined,
        };
    });
}

function functionParameters(functionLike) {
    return typeof functionLike.getParameters === 'function'
        ? parameterDefinitions(functionLike.getParameters())
        : [];
}

function sourceValue(options) {
    const counts = options.counts || { declared_args: 0, optional_args: 0 };
    return {
        name: options.name,
        visibility: options.visibility,
        visibility_intent: visibilityIntent(options.name, options.visibility),
        line_count: lineSpan(options.lineStarts, options.startIndex, options.endIndex),
        declaration_kind: 'assignment',
        value_kind: options.valueKind,
        declared_args: counts.declared_args,
        optional_args: counts.optional_args,
    };
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
        visibility_intent: visibilityIntent(options.name, options.visibility),
        line_start: lineNumberAt(options.lineStarts, options.startIndex),
        line_end: lineNumberAt(options.lineStarts, options.endIndex),
        line_count: lineSpan(options.lineStarts, options.startIndex, options.endIndex),
        parameters,
        declared_args: parameters.length,
        optional_args: parameters.filter(parameter => parameter.has_default).length,
        return_annotation: options.returnAnnotation || '',
        decorators: [],
        docstring: '',
    };
}

function callableBodyInfo(functionLike) {
    const body = typeof functionLike.getBody === 'function' ? functionLike.getBody() : undefined;
    if (body === undefined) {
        return {
            bodyNode: functionLike,
            bodyStart: functionLike.getStart(),
            bodyEnd: functionLike.getEnd(),
            endIndex: endIndexForNode(functionLike),
        };
    }
    if (Node.isBlock(body)) {
        return {
            bodyNode: body,
            bodyStart: body.getStart() + 1,
            bodyEnd: Math.max(body.getStart() + 1, body.getEnd() - 1),
            endIndex: endIndexForNode(body),
        };
    }
    return {
        bodyNode: body,
        bodyStart: body.getStart(),
        bodyEnd: body.getEnd(),
        endIndex: endIndexForNode(body),
    };
}

function addUniqueCallable(callables, callableRanges, seenIds, callable, bodyInfo, functionNode) {
    const baseQualifiedName = callable.qualified_name;
    let qualifiedName = baseQualifiedName;
    let suffix = 2;
    while (seenIds.has(callableId(callable.source_id, qualifiedName))) {
        qualifiedName = `${baseQualifiedName}#${suffix}`;
        suffix += 1;
    }
    const normalized = {
        ...callable,
        id: callableId(callable.source_id, qualifiedName),
        qualified_name: qualifiedName,
    };
    seenIds.add(normalized.id);
    callables.push(normalized);
    callableRanges.push({
        id: normalized.id,
        ownerName: normalized.owner_name,
        bodyNode: bodyInfo.bodyNode,
        functionNode,
        bodyStart: bodyInfo.bodyStart,
        bodyEnd: bodyInfo.bodyEnd,
    });
}

function propertyNameText(node) {
    if (typeof node.getName === 'function') {
        return node.getName();
    }
    if (typeof node.getNameNode === 'function') {
        return node.getNameNode().getText().replace(/^['"]|['"]$/g, '');
    }
    return '';
}

function ownerNameForObjectLiteral(objectLiteral) {
    const parent = objectLiteral.getParent();
    if (Node.isVariableDeclaration(parent)) {
        return singleBindingName(parent.getNameNode());
    }
    if (Node.isPropertyAssignment(parent)) {
        const container = parent.getParent();
        const owner = Node.isObjectLiteralExpression(container) ? ownerNameForObjectLiteral(container) : '';
        return [owner, propertyNameText(parent)].filter(Boolean).join('.');
    }
    return '';
}

function collectImports(sourceFile, filePath, sourcesRoot) {
    const imports = [];
    let statementId = 0;

    function importedSymbol(name, alias, extras = undefined) {
        return {
            name,
            alias,
            is_aliased: name !== alias,
            is_default: Boolean(extras?.isDefault),
            is_namespace: Boolean(extras?.isNamespace),
            is_star: Boolean(extras?.isStar),
        };
    }

    function addImport(importPath, importedSymbols, crossingType = 'symbol') {
        statementId += 1;
        const isRelative = importPath.startsWith('.');
        const normalizedPath = normalizedImportPath(importPath, isRelative, filePath, sourcesRoot);
        imports.push({
            path: importPath,
            is_relative: isRelative,
            normalized_path: normalizedPath,
            imported_name: importedSymbols[0]?.alias || importedSymbols[0]?.name || '',
            is_aliased: importedSymbols.some(symbol => symbol.is_aliased),
            crossing_type: crossingType,
            file_barrier_crossed: true,
            statement_id: statementId,
            join_key: normalizedPath,
            uses_joined_import: importedSymbols.length > 1,
            imported_symbols: importedSymbols,
        });
    }

    for (const declaration of sourceFile.getImportDeclarations()) {
        const importPath = moduleSpecifierValue(declaration);
        if (importPath === null) {
            continue;
        }
        const symbols = [];
        const defaultImport = declaration.getDefaultImport();
        const namespaceImport = declaration.getNamespaceImport();
        if (defaultImport !== undefined) {
            symbols.push(importedSymbol('default', defaultImport.getText(), { isDefault: true }));
        }
        if (namespaceImport !== undefined) {
            symbols.push(importedSymbol('*', namespaceImport.getText(), { isNamespace: true, isStar: true }));
        }
        for (const namedImport of declaration.getNamedImports()) {
            const name = namedImport.getName();
            const alias = namedImport.getAliasNode()?.getText() || name;
            symbols.push(importedSymbol(name, alias));
        }
        addImport(
            importPath,
            symbols.length === 0 ? [importedSymbol('*', '*', { isStar: true })] : symbols,
            symbols.length === 0 ? 'module' : 'symbol',
        );
    }

    for (const callExpression of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
        const expression = callExpression.getExpression();
        if (expression.getText() !== 'require' && expression.getText() !== 'import') {
            continue;
        }
        const firstArgument = callExpression.getArguments()[0];
        if (firstArgument === undefined || !Node.isStringLiteral(firstArgument)) {
            continue;
        }
        addImport(firstArgument.getLiteralValue(), [importedSymbol('*', '*', { isStar: true })], 'module');
    }

    return imports;
}

function sourceExport(name, kind, options) {
    const exportPath = options.path || '';
    const isRelative = exportPath.startsWith('.');
    return {
        name,
        local_name: options.localName,
        kind,
        crossing_type: options.crossingType || 'symbol',
        path: exportPath,
        is_relative: isRelative,
        normalized_path: options.normalizedPath || '',
        is_reexport: Boolean(options.isReexport),
        is_default: Boolean(options.isDefault),
        is_aliased: Boolean(options.isAliased),
        statement_id: options.statementId || 0,
    };
}

function addExport(exports, seen, value) {
    const key = [value.name, value.kind, value.normalized_path, value.is_reexport].join('\0');
    if (seen.has(key)) {
        return;
    }
    seen.add(key);
    exports.push(value);
}

function collectExports(sourceFile, filePath, sourcesRoot) {
    const exports = [];
    const seen = new Set();
    let statementId = 0;

    function normalizeExportPath(exportPath) {
        return exportPath ? normalizedImportPath(exportPath, exportPath.startsWith('.'), filePath, sourcesRoot) : '';
    }

    for (const classDeclaration of sourceFile.getClasses()) {
        if (!isExported(classDeclaration)) {
            continue;
        }
        const name = classDeclaration.isDefaultExport() ? 'default' : classDeclaration.getName() || 'default';
        addExport(exports, seen, sourceExport(name, classDeclarationIsAbstract(classDeclaration) ? 'abstract_class' : 'class', {
            localName: classDeclaration.getName() || name,
            isDefault: classDeclaration.isDefaultExport(),
        }));
    }

    for (const interfaceDeclaration of sourceFile.getInterfaces()) {
        if (isExported(interfaceDeclaration)) {
            addExport(exports, seen, sourceExport(interfaceDeclaration.getName(), 'interface', {
                localName: interfaceDeclaration.getName(),
            }));
        }
    }

    for (const typeAlias of sourceFile.getTypeAliases()) {
        if (isExported(typeAlias)) {
            addExport(exports, seen, sourceExport(typeAlias.getName(), 'type', {
                localName: typeAlias.getName(),
            }));
        }
    }

    for (const functionDeclaration of sourceFile.getFunctions()) {
        if (!isExported(functionDeclaration)) {
            continue;
        }
        const name = functionDeclaration.isDefaultExport() ? 'default' : functionDeclaration.getName() || 'default';
        addExport(exports, seen, sourceExport(name, 'function', {
            localName: functionDeclaration.getName() || name,
            isDefault: functionDeclaration.isDefaultExport(),
        }));
    }

    for (const declaration of moduleVariableDeclarations(sourceFile)) {
        const statement = declaration.getVariableStatement();
        if (statement === undefined || !statement.hasExportKeyword()) {
            continue;
        }
        for (const name of bindingNames(declaration.getNameNode())) {
            addExport(exports, seen, sourceExport(name, 'value', { localName: name }));
        }
    }

    for (const exportAssignment of sourceFile.getExportAssignments()) {
        addExport(exports, seen, sourceExport('default', 'value', {
            localName: 'default',
            isDefault: true,
        }));
    }

    for (const exportDeclaration of sourceFile.getExportDeclarations()) {
        statementId += 1;
        const exportPath = moduleSpecifierValue(exportDeclaration) || '';
        const namedExports = exportDeclaration.getNamedExports();
        if (namedExports.length === 0 && exportPath) {
            addExport(exports, seen, sourceExport('*', 'unknown', {
                localName: '*',
                path: exportPath,
                normalizedPath: normalizeExportPath(exportPath),
                crossingType: 'module',
                isReexport: true,
                statementId,
            }));
            continue;
        }
        for (const namedExport of namedExports) {
            const localName = namedExport.getName();
            const exportedName = namedExport.getAliasNode()?.getText() || localName;
            addExport(exports, seen, sourceExport(exportedName, 'unknown', {
                localName,
                path: exportPath,
                normalizedPath: normalizeExportPath(exportPath),
                crossingType: 'symbol',
                isReexport: Boolean(exportPath),
                isAliased: exportedName !== localName,
                statementId,
            }));
        }
    }

    return exports;
}

function classDeclarationIsAbstract(classDeclaration) {
    return classDeclaration.getModifiers().some(modifier => modifier.getKind() === SyntaxKind.AbstractKeyword);
}

function classPropertyIsOptional(property) {
    return Boolean(
        (typeof property.hasQuestionToken === 'function' && property.hasQuestionToken())
        || textOf(typeof property.getTypeNode === 'function' ? property.getTypeNode() : undefined).includes('undefined')
        || textOf(property.getInitializer()).match(/^(undefined|null)$/),
    );
}

function sourceClassMethod(method, lineStarts, name = propertyNameText(method)) {
    const parameters = functionParameters(method);
    const visibility = visibilityFromModifiers(method);
    return {
        name,
        visibility,
        visibility_intent: visibilityIntent(name, visibility),
        line_count: lineSpan(lineStarts, method.getStart(), endIndexForNode(method)),
        declared_args: parameters.length,
        optional_args: parameters.filter(parameter => parameter.has_default).length,
    };
}

function collectClasses(sourceFile, lineStarts) {
    const classes = [];
    const abstractClasses = [];
    const classRanges = [];

    for (const classDeclaration of sourceFile.getClasses()) {
        const name = classDeclaration.getName() || 'default';
        const visibility = moduleVisibility(classDeclaration);
        classRanges.push({
            start: classDeclaration.getStart(),
            end: classDeclaration.getEnd(),
        });

        const properties = new Map();
        for (const property of classDeclaration.getProperties()) {
            properties.set(propertyNameText(property), classPropertyIsOptional(property));
        }
        for (const constructorDeclaration of classDeclaration.getConstructors()) {
            for (const parameter of constructorDeclaration.getParameters()) {
                if (parameter.isParameterProperty()) {
                    const parameterName = singleBindingName(parameter.getNameNode()) || parameter.getNameNode().getText();
                    properties.set(parameterName, parameter.isOptional() || parameter.getInitializer() !== undefined);
                }
            }
        }

        const concreteMethods = [];
        const abstractMethods = [];
        for (const constructorDeclaration of classDeclaration.getConstructors()) {
            concreteMethods.push(sourceClassMethod(constructorDeclaration, lineStarts, 'constructor'));
        }
        for (const method of classDeclaration.getMethods()) {
            const methodValue = sourceClassMethod(method, lineStarts);
            if (method.getBody() === undefined || method.getModifiers().some(modifier => modifier.getKind() === SyntaxKind.AbstractKeyword)) {
                abstractMethods.push(methodValue);
            } else {
                concreteMethods.push(methodValue);
            }
        }

        const base = {
            name,
            visibility,
            visibility_intent: visibilityIntent(name, visibility),
            properties: Array.from(properties, ([propertyName, isOptional]) => ({
                name: propertyName,
                is_optional: Boolean(isOptional),
            })),
            line_count: lineSpan(lineStarts, classDeclaration.getStart(), endIndexForNode(classDeclaration)),
        };

        if (classDeclarationIsAbstract(classDeclaration)) {
            abstractClasses.push({
                ...base,
                abstract_methods: abstractMethods,
                concrete_methods: concreteMethods,
            });
        } else {
            classes.push({
                ...base,
                methods: concreteMethods,
            });
        }
    }

    return { classes, abstractClasses, classRanges };
}

function collectSignaturesFromMembers(members, lineStarts) {
    const signatures = [];
    for (const member of members) {
        let kind = '';
        if (Node.isCallSignatureDeclaration(member)) {
            kind = 'call';
        } else if (Node.isConstructSignatureDeclaration(member)) {
            kind = 'construct';
        } else if (Node.isIndexSignatureDeclaration(member)) {
            kind = 'index';
        }
        if (!kind) {
            continue;
        }
        const parameters = typeof member.getParameters === 'function' ? functionParameters(member) : [];
        signatures.push({
            kind,
            line_count: lineSpan(lineStarts, member.getStart(), endIndexForNode(member)),
            declared_args: parameters.length,
            optional_args: parameters.filter(parameter => parameter.has_default).length,
        });
    }
    return signatures;
}

function collectInterfaces(sourceFile, lineStarts) {
    return sourceFile.getInterfaces().map(interfaceDeclaration => {
        const visibility = moduleVisibility(interfaceDeclaration);
        const properties = interfaceDeclaration.getProperties().map(property => ({
            name: propertyNameText(property),
            is_optional: Boolean(typeof property.hasQuestionToken === 'function' && property.hasQuestionToken()),
        }));
        const methods = interfaceDeclaration.getMethods().map(method => sourceClassMethod(method, lineStarts));
        return {
            name: interfaceDeclaration.getName(),
            visibility,
            visibility_intent: visibilityIntent(interfaceDeclaration.getName(), visibility),
            methods,
            properties,
            signatures: collectSignaturesFromMembers(interfaceDeclaration.getMembers(), lineStarts),
            line_count: lineSpan(lineStarts, interfaceDeclaration.getStart(), endIndexForNode(interfaceDeclaration)),
        };
    });
}

function collectTypes(sourceFile, lineStarts) {
    return sourceFile.getTypeAliases().map(typeAlias => {
        const visibility = moduleVisibility(typeAlias);
        const typeNode = typeAlias.getTypeNode();
        const members = Node.isTypeLiteral(typeNode) ? typeNode.getMembers() : [];
        const properties = members.filter(member => Node.isPropertySignature(member)).map(property => ({
            name: propertyNameText(property),
            is_optional: Boolean(typeof property.hasQuestionToken === 'function' && property.hasQuestionToken()),
        }));
        return {
            name: typeAlias.getName(),
            visibility,
            visibility_intent: visibilityIntent(typeAlias.getName(), visibility),
            properties,
            signatures: collectSignaturesFromMembers(members, lineStarts),
            line_count: lineSpan(lineStarts, typeAlias.getStart(), endIndexForNode(typeAlias)),
        };
    });
}

function moduleVariableDeclarations(sourceFile) {
    return sourceFile.getVariableDeclarations().filter(declaration => {
        const statement = declaration.getVariableStatement();
        return statement !== undefined && statement.getParent() === sourceFile;
    });
}

function collectValues(sourceFile, lineStarts) {
    const values = [];
    for (const declaration of sourceFile.getVariableDeclarations()) {
        const initializer = declaration.getInitializer();
        const valueKind = expressionValueKind(initializer);
        const expression = initializer === undefined ? undefined : unwrapExpression(initializer);
        const parameters = expression !== undefined && (Node.isArrowFunction(expression) || Node.isFunctionExpression(expression))
            ? functionParameters(expression)
            : [];
        const counts = {
            declared_args: parameters.length,
            optional_args: parameters.filter(parameter => parameter.has_default).length,
        };
        const variableStatement = declaration.getVariableStatement();
        const visibility = variableStatement !== undefined && variableStatement.getParent() === sourceFile
            ? moduleVisibility(variableStatement)
            : 'private';
        for (const name of bindingNames(declaration.getNameNode())) {
            values.push(sourceValue({
                name,
                visibility,
                startIndex: declaration.getStart(),
                endIndex: endIndexForNode(declaration),
                lineStarts,
                valueKind,
                counts,
            }));
        }
    }

    for (const exportAssignment of sourceFile.getExportAssignments()) {
        const expression = unwrapExpression(exportAssignment.getExpression());
        if (!Node.isArrowFunction(expression) && !Node.isFunctionExpression(expression)) {
            continue;
        }
        const parameters = functionParameters(expression);
        values.push(sourceValue({
            name: 'default',
            visibility: 'public',
            startIndex: exportAssignment.getStart(),
            endIndex: endIndexForNode(exportAssignment),
            lineStarts,
            valueKind: 'callable',
            counts: {
                declared_args: parameters.length,
                optional_args: parameters.filter(parameter => parameter.has_default).length,
            },
        }));
    }
    return values;
}

function collectFunctions(sourceFile, lineStarts) {
    const functions = [];
    const seen = new Set();

    function addFunction(name, node, parameters, visibility) {
        if (!name || seen.has(name)) {
            return;
        }
        seen.add(name);
        functions.push({
            name,
            visibility,
            visibility_intent: visibilityIntent(name, visibility),
            line_count: lineSpan(lineStarts, node.getStart(), endIndexForNode(node)),
            declared_args: parameters.length,
            optional_args: parameters.filter(parameter => parameter.has_default).length,
        });
    }

    for (const functionDeclaration of sourceFile.getFunctions()) {
        const name = functionDeclaration.getName() || (functionDeclaration.isDefaultExport() ? 'default' : '');
        addFunction(name, functionDeclaration, functionParameters(functionDeclaration), moduleVisibility(functionDeclaration));
    }

    for (const declaration of moduleVariableDeclarations(sourceFile)) {
        const name = singleBindingName(declaration.getNameNode());
        const initializer = declaration.getInitializer();
        const expression = initializer === undefined ? undefined : unwrapExpression(initializer);
        if (name && expression !== undefined && (Node.isArrowFunction(expression) || Node.isFunctionExpression(expression))) {
            addFunction(name, declaration, functionParameters(expression), moduleVisibility(declaration.getVariableStatement()));
        }
    }

    for (const exportAssignment of sourceFile.getExportAssignments()) {
        const expression = unwrapExpression(exportAssignment.getExpression());
        if (Node.isArrowFunction(expression) || Node.isFunctionExpression(expression)) {
            addFunction('default', exportAssignment, functionParameters(expression), 'public');
        }
    }
    return functions;
}

function nearestFunctionLike(node) {
    let current = node;
    while (current !== undefined) {
        if (
            Node.isFunctionDeclaration(current)
            || Node.isFunctionExpression(current)
            || Node.isArrowFunction(current)
            || Node.isMethodDeclaration(current)
            || Node.isConstructorDeclaration(current)
        ) {
            return current;
        }
        current = current.getParent();
    }
    return undefined;
}

function callableNameForExpression(expression, lineStarts) {
    const parent = expression.getParent();
    if (Node.isVariableDeclaration(parent)) {
        const name = singleBindingName(parent.getNameNode());
        if (name) {
            return { name, qualifiedName: name, ownerName: '', visibility: moduleVisibility(parent.getVariableStatement()) };
        }
    }
    if (Node.isPropertyDeclaration(parent)) {
        const classDeclaration = parent.getFirstAncestorByKind(SyntaxKind.ClassDeclaration);
        const ownerName = classDeclaration?.getName() || 'default';
        const name = propertyNameText(parent);
        return {
            name,
            qualifiedName: `${ownerName}.${name}`,
            ownerName,
            visibility: visibilityFromModifiers(parent),
        };
    }
    if (Node.isPropertyAssignment(parent) || Node.isShorthandPropertyAssignment(parent)) {
        const objectLiteral = parent.getParent();
        const ownerName = Node.isObjectLiteralExpression(objectLiteral) ? ownerNameForObjectLiteral(objectLiteral) : '';
        const name = propertyNameText(parent);
        return {
            name,
            qualifiedName: [ownerName, name].filter(Boolean).join('.') || name,
            ownerName,
            visibility: 'private',
        };
    }
    if (Node.isExportAssignment(parent)) {
        return { name: 'default', qualifiedName: 'default', ownerName: '', visibility: 'public' };
    }
    const line = lineNumberAt(lineStarts, expression.getStart());
    const column = expression.getStart() - lineStarts[line - 1];
    const name = `<anonymous>@${line}:${column}`;
    return { name, qualifiedName: name, ownerName: '', visibility: 'private' };
}

function collectCallables(sourceFile, lineStarts, sourceId) {
    const callables = [];
    const callableRanges = [];
    const seenIds = new Set();

    function addFunctionLike(node, nameInfo, kind, startNode = node) {
        const bodyInfo = callableBodyInfo(node);
        addUniqueCallable(callables, callableRanges, seenIds, sourceCallable({
            sourceId,
            name: nameInfo.name,
            qualifiedName: nameInfo.qualifiedName,
            ownerName: nameInfo.ownerName,
            kind,
            visibility: nameInfo.visibility,
            startIndex: startNode.getStart(),
            endIndex: bodyInfo.endIndex,
            lineStarts,
            parameters: functionParameters(node),
            returnAnnotation: textOf(typeof node.getReturnTypeNode === 'function' ? node.getReturnTypeNode() : undefined),
        }), bodyInfo, node);
    }

    for (const functionDeclaration of sourceFile.getFunctions()) {
        if (functionDeclaration.getBody() === undefined) {
            continue;
        }
        const name = functionDeclaration.getName() || (functionDeclaration.isDefaultExport() ? 'default' : '');
        if (name) {
            addFunctionLike(functionDeclaration, {
                name,
                qualifiedName: name,
                ownerName: '',
                visibility: moduleVisibility(functionDeclaration),
            }, 'function');
        }
    }

    for (const classDeclaration of sourceFile.getClasses()) {
        const className = classDeclaration.getName() || 'default';
        for (const constructorDeclaration of classDeclaration.getConstructors()) {
            if (constructorDeclaration.getBody() !== undefined) {
                addFunctionLike(constructorDeclaration, {
                    name: 'constructor',
                    qualifiedName: `${className}.constructor`,
                    ownerName: className,
                    visibility: visibilityFromModifiers(constructorDeclaration),
                }, 'constructor');
            }
        }
        for (const method of classDeclaration.getMethods()) {
            if (method.getBody() === undefined) {
                continue;
            }
            const name = method.getName();
            const isStatic = method.getModifiers().some(modifier => modifier.getKind() === SyntaxKind.StaticKeyword);
            addFunctionLike(method, {
                name,
                qualifiedName: `${className}.${name}`,
                ownerName: className,
                visibility: visibilityFromModifiers(method),
            }, isStatic ? 'staticmethod' : 'method');
        }
    }

    for (const expression of [
        ...sourceFile.getDescendantsOfKind(SyntaxKind.ArrowFunction),
        ...sourceFile.getDescendantsOfKind(SyntaxKind.FunctionExpression),
    ]) {
        const nameInfo = callableNameForExpression(expression, lineStarts);
        const parent = expression.getParent();
        const named = Node.isVariableDeclaration(parent)
            || Node.isPropertyDeclaration(parent)
            || Node.isPropertyAssignment(parent)
            || Node.isShorthandPropertyAssignment(parent)
            || Node.isExportAssignment(parent);
        addFunctionLike(expression, nameInfo, named ? 'callable_value' : 'anonymous', named ? parent : expression);
    }

    for (const method of sourceFile.getDescendantsOfKind(SyntaxKind.MethodDeclaration)) {
        const objectLiteral = method.getParent();
        if (!Node.isObjectLiteralExpression(objectLiteral) || method.getBody() === undefined) {
            continue;
        }
        const ownerName = ownerNameForObjectLiteral(objectLiteral);
        const name = method.getName();
        addFunctionLike(method, {
            name,
            qualifiedName: [ownerName, name].filter(Boolean).join('.') || name,
            ownerName,
            visibility: 'private',
        }, 'callable_value');
    }

    return { callables, callableRanges };
}

function expressionName(expression) {
    const text = expression.getText();
    return text.split('.').pop() || text;
}

function collectCalls(sourceFile, lineStarts, sourceId, callableRanges, callables) {
    const byName = new Map();
    const byQualifiedName = new Map();
    const constructorsByName = new Map();
    for (const callable of callables) {
        byQualifiedName.set(callable.qualified_name, callable.id);
        if (['function', 'callable_value'].includes(callable.kind)) {
            byName.set(callable.name, callable.id);
        }
        if (callable.kind === 'constructor') {
            constructorsByName.set(callable.owner_name, callable.id);
        }
    }

    const rangesByFunction = new Map();
    for (const range of callableRanges) {
        rangesByFunction.set(range.functionNode, range);
    }
    const calls = [];

    function addCall(node, expression, isConstructor) {
        const nearest = nearestFunctionLike(node);
        const range = rangesByFunction.get(nearest);
        if (range === undefined) {
            return;
        }
        const expressionText = expression.getText();
        const targetName = expressionName(expression);
        let targetCallableId = '';
        let resolution = 'unresolved';
        if (isConstructor && constructorsByName.has(expressionText)) {
            targetCallableId = constructorsByName.get(expressionText);
            resolution = 'resolved';
        } else if (byQualifiedName.has(expressionText)) {
            targetCallableId = byQualifiedName.get(expressionText);
            resolution = 'resolved';
        } else if (expressionText.startsWith('this.') && range.ownerName) {
            const qualifiedName = `${range.ownerName}.${expressionText.slice('this.'.length)}`;
            if (byQualifiedName.has(qualifiedName)) {
                targetCallableId = byQualifiedName.get(qualifiedName);
                resolution = 'resolved';
            }
        } else if (byName.has(expressionText)) {
            targetCallableId = byName.get(expressionText);
            resolution = 'resolved';
        }
        calls.push({
            source_callable_id: range.id,
            target_callable_id: targetCallableId,
            source_id: sourceId,
            line: lineNumberAt(lineStarts, node.getStart()),
            expression: expressionText,
            resolution,
            target_name: targetName,
        });
    }

    for (const callExpression of sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression)) {
        addCall(callExpression, callExpression.getExpression(), false);
    }
    for (const newExpression of sourceFile.getDescendantsOfKind(SyntaxKind.NewExpression)) {
        const expression = newExpression.getExpression();
        if (expression !== undefined) {
            addCall(newExpression, expression, true);
        }
    }
    return calls;
}

function collectCallableGraph(sourceFile, lineStarts, sourceId) {
    const { callables, callableRanges } = collectCallables(sourceFile, lineStarts, sourceId);
    return {
        values: collectValues(sourceFile, lineStarts),
        callables,
        calls: collectCalls(sourceFile, lineStarts, sourceId, callableRanges, callables),
    };
}

function publicSymbolCount(exports) {
    return new Set(exports.filter(value => !value.is_reexport).map(value => value.name)).size;
}

function extractFile(filePath, sourcesRoot, sourceId = null) {
    const content = fs.readFileSync(filePath, 'utf8');
    let sourceFile;
    let lineStarts;
    let resolvedSourceId;
    let classes;
    let abstractClasses;
    let imports;
    let exports;
    let callableGraph;
    try {
        sourceFile = parseSourceFile(path.resolve(filePath), content);
        lineStarts = buildLineStarts(content);
        resolvedSourceId = sourceId || sourceIdForPath(filePath, sourcesRoot);
        ({ classes, abstractClasses } = collectClasses(sourceFile, lineStarts));
        imports = collectImports(sourceFile, filePath, sourcesRoot);
        exports = collectExports(sourceFile, filePath, sourcesRoot);
        callableGraph = collectCallableGraph(sourceFile, lineStarts, resolvedSourceId);
    } catch (error) {
        if (shouldReturnEmptySourceFile(error)) {
            return emptySourceFile(content);
        }
        throw error;
    }

    return {
        imports,
        exports,
        classes,
        interfaces: collectInterfaces(sourceFile, lineStarts),
        types: collectTypes(sourceFile, lineStarts),
        abstract_classes: abstractClasses,
        functions: collectFunctions(sourceFile, lineStarts),
        values: callableGraph.values,
        callables: callableGraph.callables,
        calls: callableGraph.calls,
        line_count: content.split('\n').length,
        code_line_count: codeLineCount(content),
        public_symbol_count: publicSymbolCount(exports),
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
