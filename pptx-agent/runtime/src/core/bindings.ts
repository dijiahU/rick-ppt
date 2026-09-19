import type {SceneNode,Environment} from './types';
import {Expressions} from './expressions';
export function bindNode(node:SceneNode,environment:Environment,expressions:Expressions){const result={...node,...expressions.value(node.props??{},environment)};for(const [key,expr]of Object.entries(node.bind??{}))result[key]=expressions.evaluate(expr.expr,environment);result.visible=node.when?!!expressions.evaluate(node.when.expr,environment):result.visibility!==false;return result;}
