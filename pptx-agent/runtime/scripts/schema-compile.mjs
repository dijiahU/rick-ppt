import Ajv from 'ajv';
import standalone from 'ajv/dist/standalone/index.js';
import {readFileSync,writeFileSync} from 'node:fs';
const schema=JSON.parse(readFileSync('../skills/pptx/schemas/interactive-slide.schema.json','utf8'));
const ajv=new Ajv({strict:false,allErrors:true,unicode:false,code:{source:true,esm:true}});
writeFileSync('src/core/schema-validator.js',standalone(ajv,ajv.compile(schema)));
