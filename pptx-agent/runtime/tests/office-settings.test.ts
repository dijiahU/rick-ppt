import {afterEach,describe,expect,it,vi} from 'vitest';
import {identity,saveIdentity,type Identity} from '../src/office/settings';

const persisted:Identity={deckId:'deck-example',sceneId:'cnn-example',instanceId:'82a9efbc-445d-4dce-9bfe-011203040506',schemaVersion:1,specHash:'a'.repeat(64)};
function mockOffice(values:Record<string,unknown>={}){
 const settings={get:vi.fn((key:string)=>({...persisted,...values} as Record<string,unknown>)[key]),set:vi.fn(),saveAsync:vi.fn((callback:(result:any)=>void)=>callback({status:'succeeded'}))};
 const office={onReady:vi.fn(async()=>{}),context:{host:'PowerPoint',document:{settings}}};
 vi.stubGlobal('location',{pathname:'/content.html'});vi.stubGlobal('Office',office);
 return{office,settings};
}
afterEach(()=>vi.unstubAllGlobals());

describe('Office property-bag identity contract (mock host, not desktop proof)',()=>{
 it.each(['null','false','123'])('preserves JSON-looking string %s without a second decode',async value=>{
  mockOffice({deckId:value,sceneId:value,instanceId:value,specHash:value});
  expect(await identity()).toEqual({deckId:value,sceneId:value,instanceId:value,specHash:value,schemaVersion:1});
 });
 it('awaits Office readiness before accessing the host document and does not rewrite existing settings',async()=>{
  const {office,settings}=mockOffice();let ready!:()=>void;
  office.onReady.mockImplementation(()=>new Promise<void>(resolve=>{ready=resolve;}));
  const loading=identity();expect(settings.get).not.toHaveBeenCalled();ready();
  expect(await loading).toEqual(persisted);expect(office.onReady).toHaveBeenCalledOnce();
  expect(settings.get.mock.calls.map(([key])=>key).sort()).toEqual(Object.keys(persisted).sort());
  expect(settings.set).not.toHaveBeenCalled();expect(settings.saveAsync).not.toHaveBeenCalled();
 });
 it.each([
  ['deckId',null],['sceneId',false],['sceneId',123],['instanceId',{}],['specHash',[]],['deckId',''],['sceneId','  '],['instanceId',undefined]
 ])('rejects invalid %s value %j',async(key,value)=>{
  mockOffice({[key as string]:value});await expect(identity()).rejects.toThrow(`Invalid content identity ${key}`);
 });
 it.each(['1',null,undefined,NaN,1.5,2])('rejects non-supported numeric schemaVersion %s',async schemaVersion=>{
  mockOffice({schemaVersion});await expect(identity()).rejects.toThrow('Invalid content identity schemaVersion');
 });
 it('keeps ordinary strings verbatim rather than treating quoted content as a legacy serialization',async()=>{
  mockOffice({sceneId:'"cnn-example"'});expect((await identity())?.sceneId).toBe('"cnn-example"');
 });
 it('bypasses Office entirely in standalone preview',async()=>{
  vi.stubGlobal('location',{pathname:'/preview.html'});vi.stubGlobal('Office',undefined);
  expect(await identity()).toBeNull();
 });
 it('reports missing Office.js on content pages',async()=>{
  vi.stubGlobal('location',{pathname:'/content.html'});vi.stubGlobal('Office',undefined);
  await expect(identity()).rejects.toThrow('Office.js is unavailable');
 });
 it('rejects the wrong Office host before reading settings',async()=>{
  const{office,settings}=mockOffice();office.context.host='Word';
  await expect(identity()).rejects.toThrow('PowerPoint is required');expect(settings.get).not.toHaveBeenCalled();
 });
});

describe('explicit identity save (mock callbacks)',()=>{
 it('writes typed settings and waits for a successful save callback',async()=>{
  const{settings}=mockOffice();let finish!:(result:any)=>void;
  settings.saveAsync.mockImplementation(callback=>{finish=callback;});let complete=false;
  const saving=saveIdentity(persisted).then(()=>{complete=true;});
  expect(settings.set.mock.calls).toEqual(Object.entries(persisted));expect(settings.saveAsync).toHaveBeenCalledOnce();
  await Promise.resolve();expect(complete).toBe(false);finish({status:'succeeded'});await saving;expect(complete).toBe(true);
 });
 it.each([
  [{status:'failed',error:{message:'Document is read-only'}},'Document is read-only'],
  [{status:'failed'},'Settings persistence failed']
 ])('propagates Office save failure %j',async(result,message)=>{
  const{settings}=mockOffice();settings.saveAsync.mockImplementation(callback=>callback(result));
  await expect(saveIdentity(persisted)).rejects.toThrow(message as string);
 });
});
