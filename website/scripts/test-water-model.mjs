import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import ts from 'typescript';
const ex={};new Function('exports',ts.transpileModule(readFileSync(new URL('../lib/water-model.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(ex);
const {WaterField,advanceSpring,poolTarget,poolHomes,safelight,driftOffset,lampFalloff,keepClear}=ex;
const water=new WaterField(80,48);assert.equal(water.energy(),0);water.disturb(.5,.5,1,.03);for(let n=0;n<20;n++)water.step();assert.ok(water.energy()>0);assert.notEqual(water.sample(.56,.5),0,'Disturbances propagate beyond their origin');const energy=water.energy();for(let n=0;n<1800;n++)water.step();assert.ok(water.energy()<energy*.01,'Water settles after input stops');
for(let n=0;n<2000;n++){if(n%7===0){water.splash((n%13)/12,(n%11)/10,.12,.1,n%2?1:-1);water.disturb((n%101)/100,((n*3)%97)/96,1.4,.03);}water.step();}assert.ok([...water.height,...water.velocity].every(Number.isFinite));assert.ok(water.height.every(x=>Math.abs(x)<=3));assert.ok(water.velocity.every(x=>Math.abs(x)<=2.5));const pixels=water.encode();assert.equal(pixels.length,80*48*4);for(let i=0;i<water.height.length;i++){const decoded=((pixels[i*4]*256+pixels[i*4+1])/65535-.5)*6;assert.ok(Math.abs(decoded-water.height[i])<.0001);assert.equal(pixels[i*4+3],255);}
const invalid=new WaterField(32,24);invalid.disturb(NaN,Infinity,1);assert.equal(invalid.energy(),0);invalid.disturb(-20,30,100,1);for(let n=0;n<100;n++)invalid.step();assert.ok(invalid.height.every(Number.isFinite));
const spring={value:0,velocity:0};for(let n=0;n<10;n++)advanceSpring(spring,100,1/60,105,17);const before=spring.value,velocity=spring.velocity;assert.ok(before>0&&before<100);advanceSpring(spring,-100,1/60,105,17);assert.ok(Math.abs(spring.value-before)<20,'Rapid reversal continues from the current position');assert.ok(spring.velocity!==0&&velocity!==0);for(let n=0;n<300;n++)advanceSpring(spring,-100,1/60,105,17);assert.ok(Math.abs(spring.value+100)<.01);assert.ok(Math.abs(spring.velocity)<.01);
// Prints rest clear of the headline and inside the tray in every layout, and keep their place while they drift.
for(const [aspect,width,height] of [[1.7,1440,848],[1,900,848],[.375,390,1040]]){
 const homes=poolHomes(aspect);assert.equal(homes.length,4);
 for(const home of homes){assert.ok(Math.abs(home.x)+home.size/2<=.5+.02,'A resting print stays inside the tray');assert.ok(home.y<.42&&home.y>-.3);}
 assert.ok(homes.every(home=>aspect>=1.25?home.x>-.02||home.y>.2:home.y>0),'The headline area stays clear');
 assert.ok(homes.every(home=>home.size>=.3),'Prints are large enough to read');
 for(let i=0;i<4;i++)for(let j=i+1;j<4;j++){const a=homes[i],b=homes[j];assert.ok(Math.abs(a.x-b.x)*width>60||Math.abs(a.y-b.y)*height>60,'No two prints rest on the same spot');}
 const lamp=safelight(aspect);assert.ok(lamp.x>.5&&lamp.x<1&&lamp.y>0&&lamp.y<.2,'The safelight hangs top right, below the header');
 const cardWidth=width*.7;
 for(let i=0;i<4;i++){
  const rest=poolTarget(i,null,homes,width,height,cardWidth,0);assert.equal(rest.alpha,1);assert.ok(Math.abs(rest.scale*cardWidth-homes[i].size*width)<.5,'A floating print is as wide as its place in the tray');
  for(const time of [0,13,47,311,2900]){const pose=poolTarget(i,null,homes,width,height,cardWidth,time);assert.ok(Math.abs(pose.x-homes[i].x*width)<=width*.043&&Math.abs(pose.y-homes[i].y*height)<=height*.045,'Drift stays close to home');assert.ok(Math.abs(pose.roll-homes[i].roll)<=3.5);}
  const span=[0,4,9,15,22,31].map(time=>poolTarget(i,null,homes,width,height,cardWidth,time).x);assert.ok(Math.max(...span)-Math.min(...span)>width*.015,'Prints visibly drift within half a minute');
  const waiting=poolTarget(i,(i+1)%4,homes,width,height,cardWidth,5);assert.ok(waiting.alpha<.5&&waiting.scale===rest.scale,'Prints left in the bath dim, without a change of scale that would force a redraw every frame');
 }
 assert.deepEqual(poolTarget(2,2,homes,width,height,cardWidth,99),{x:0,y:0,scale:1,roll:0,pitch:0,alpha:1});
 assert.equal(poolTarget(2,2,homes,width,height,cardWidth,99,1.3).scale,1.3,'The lifted print is enlarged by the lift factor');
}
// A print never covers the headline: wherever drift takes it, it is moved the shortest way out, right or down.
{const box={left:-664,top:-320,right:-140,bottom:120},wide=poolHomes(1.7);
 assert.deepEqual(keepClear(300,-100,200,120,box),{x:300,y:-100},'Clear of the headline: untouched');
 assert.deepEqual(keepClear(40,-100,200,120,box),{x:60,y:-100},'Pushed right by the smaller distance');
 assert.deepEqual(keepClear(-400,200,220,130,box),{x:-400,y:250},'Pushed down by the smaller distance');
 assert.deepEqual(keepClear(40,-100,200,120,null),{x:40,y:-100});
 for(let i=0;i<4;i++)for(let time=0;time<600;time+=1.7){
  const pose=poolTarget(i,null,wide,1440,848,954,time,1.3,box,546),turn=Math.abs(pose.roll)*Math.PI/180,w=954*pose.scale,h=546*pose.scale,halfW=(w*Math.cos(turn)+h*Math.sin(turn))/2,halfH=(w*Math.sin(turn)+h*Math.cos(turn))/2;
  assert.ok(pose.x-halfW>=box.right-.001||pose.y-halfH>=box.bottom-.001,`Print ${i} stays off the headline at ${time}s`);
 }}
assert.notDeepEqual(driftOffset(0,10),driftOffset(1,10));assert.notDeepEqual(driftOffset(0,10),driftOffset(0,40));
assert.equal(lampFalloff(.8,.1,.8,.1,1.6,1.5),1);assert.ok(lampFalloff(.1,.9,.8,.1,1.6,1.5)<lampFalloff(.6,.3,.8,.1,1.6,1.5),'Light falls off with distance from the lamp');
const splashed=new WaterField(80,48);splashed.splash(.5,.5,.12,.1);assert.ok(splashed.velocity.some(v=>v>0)&&splashed.velocity.some(v=>v<0),'A print breaking the surface pushes down at its centre and up around its edge');
console.log('PASS: wave propagation, damping, 2,000-step rapid input stability, exact height texture encoding, invalid input containment, continuous spring reversals, four-print tray layouts for wide/medium/tall stages, visible but bounded drift that never covers the headline, waiting and lifted poses, lamp falloff and print splash.');
