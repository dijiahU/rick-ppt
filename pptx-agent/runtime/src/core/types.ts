export type JSONValue = null | boolean | number | string | JSONValue[] | {[key:string]:JSONValue};
export type Dict = Record<string, any>;
export type Expression = {expr:string};
export type EventContext = {type:string;target:string;timestamp:number;x?:number;y?:number;localX?:number;localY?:number;key?:string;value?:any;deltaY?:number;shiftKey?:boolean;ctrlKey?:boolean;altKey?:boolean;metaKey?:boolean;[key:string]:any};
export type Action = {type:string;path?:string;value?:any;actions?:Action[];then?:Action[];else?:Action[];condition?:Expression;[key:string]:any};
export type SceneNode = {id:string;type:string;children?:SceneNode[];bind?:Record<string,Expression>;when?:Expression;repeat?:{source:Expression;item:string;key:Expression};props?:Dict;component?:string;[key:string]:any};
export type Scene = {schemaVersion:1;id:string;viewport:{width:number;height:number};nodes:SceneNode[];theme?:Dict;assets?:Record<string,{path:string;sha256?:string;bytes?:number;type?:string}>;initialState?:Dict;derivedState?:Record<string,Expression>;dataSources?:Dict;interactions?:{target:string;event:string;actions:Action[];when?:Expression}[];behaviors?:Dict[];timelines?:Dict[];functions?:Record<string,{params:string[];expr:string}>;components?:Record<string,{nodes:SceneNode[]}>;plugins?:Dict[];requires?:string[];testPlan?:Dict[];runtimeOptions?:Dict};
export type Environment = {state:Dict;data:Dict;locals?:Dict;event?:Dict};
