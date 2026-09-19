import validate from './schema-validator.js';
import {safeObject} from './state';
import type {Scene,SceneNode} from './types';

export function migrateScene(value:any):Scene {if(value?.schemaVersion!==1)throw new Error(`Unsupported scene schema version: ${value?.schemaVersion}`);return value;}
export function validateScene(input:any):Scene {safeObject(input);if(JSON.stringify(input).length>8*1024*1024)throw new Error('Scene exceeds 8 MiB');if(!validate(input))throw new Error('Invalid scene: '+JSON.stringify(validate.errors));const value=migrateScene(input);let count=0;const ids=new Set<string>();function walk(nodes:SceneNode[],depth=0){if(depth>32)throw new Error('Scene nesting exceeded');for(const n of nodes){if(++count>10000)throw new Error('Node count exceeded');if(ids.has(n.id))throw new Error(`Duplicate node: ${n.id}`);ids.add(n.id);walk(n.children??[],depth+1);}}walk(value.nodes);return value;}
