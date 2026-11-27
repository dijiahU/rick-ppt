/** Damped height-field water and interruptible spring motion. No DOM dependencies. */
export const clamp=(value:number,min:number,max:number)=>Math.max(min,Math.min(max,value));
export class WaterField{
 readonly height:Float32Array;readonly velocity:Float32Array;private next:Float32Array;readonly pixels:Uint8Array;
 constructor(readonly width=160,readonly depth=96){this.height=new Float32Array(width*depth);this.velocity=new Float32Array(width*depth);this.next=new Float32Array(width*depth);this.pixels=new Uint8Array(width*depth*4);}
 disturb(x:number,y:number,power=.7,radius=.025){if(![x,y,power,radius].every(Number.isFinite))return;x=clamp(x,0,1);y=clamp(y,0,1);radius=clamp(radius,.008,.2);power=clamp(power,-2,2);const rx=radius*this.width,ry=radius*this.depth;const cx=x*(this.width-1),cy=y*(this.depth-1);for(let j=Math.max(1,Math.floor(cy-ry*3));j<Math.min(this.depth-1,cy+ry*3);j++)for(let i=Math.max(1,Math.floor(cx-rx*3));i<Math.min(this.width-1,cx+rx*3);i++){const d=((i-cx)/rx)**2+((j-cy)/ry)**2;const k=j*this.width+i;this.velocity[k]=clamp(this.velocity[k]+power*Math.exp(-d*1.7),-2,2);}}
 /** A print leaving or entering the bath: a push at its centre and a ring where its edges break the surface. */
 splash(x:number,y:number,halfWidth:number,halfHeight:number,power=.8){this.disturb(x,y,-power*.55,Math.max(halfWidth,halfHeight)*.55);for(let n=0;n<14;n++){const angle=n/14*Math.PI*2;this.disturb(x+Math.cos(angle)*halfWidth,y+Math.sin(angle)*halfHeight,power*.5,.02);}}
 step(){const {width:w,depth:d,height:h,velocity:v,next:n}=this;for(let y=1;y<d-1;y++)for(let x=1;x<w-1;x++){const i=y*w+x;const lap=h[i-1]+h[i+1]+h[i-w]+h[i+w]-4*h[i];const edge=Math.min(x,y,w-1-x,d-1-y);v[i]=clamp((v[i]+lap*.24)*(edge<8?.9+.011*edge:.986),-2.5,2.5);n[i]=clamp((h[i]+v[i])*.999,-3,3);}h.set(n);}
 sample(x:number,y:number){x=clamp(x,0,1)*(this.width-1);y=clamp(y,0,1)*(this.depth-1);const ix=Math.floor(x),iy=Math.floor(y),fx=x-ix,fy=y-iy;const a=this.height[iy*this.width+ix],b=this.height[iy*this.width+Math.min(ix+1,this.width-1)],c=this.height[Math.min(iy+1,this.depth-1)*this.width+ix],d=this.height[Math.min(iy+1,this.depth-1)*this.width+Math.min(ix+1,this.width-1)];return (a+(b-a)*fx)*(1-fy)+(c+(d-c)*fx)*fy;}
 encode(){for(let i=0;i<this.height.length;i++){const value=Math.round((clamp(this.height[i],-3,3)/6+.5)*65535);const p=i*4;this.pixels[p]=value>>8;this.pixels[p+1]=value&255;this.pixels[p+2]=Math.round(clamp(Math.abs(this.velocity[i])*.65,0,1)*255);this.pixels[p+3]=255;}return this.pixels;}
 energy(){let total=0;for(let i=0;i<this.height.length;i++)total+=this.height[i]**2+this.velocity[i]**2;return total;}
}
export type Spring={value:number;velocity:number};
export function advanceSpring(s:Spring,target:number,dt:number,stiffness=90,damping=18){dt=clamp(dt,0,1/30);s.velocity+=(target-s.value)*stiffness*dt;s.velocity*=Math.exp(-damping*dt);s.value+=s.velocity*dt;return s.value;}
export type CardPose={x:number;y:number;scale:number;roll:number;pitch:number;alpha:number};
/** A print's resting place in the tray: fractions of the stage measured from its centre; `size` is print width over stage width. */
export type PoolHome={x:number;y:number;roll:number;size:number};
// Four prints, large enough to read what is on them: the diagram beside the headline, three along the bottom.
// Later prints lie over earlier ones, so the bottom row runs left to right and every name tag stays on top.
const WIDE:PoolHome[]=[{x:.19,y:-.135,roll:-3,size:.4},{x:-.32,y:.325,roll:-3,size:.31},{x:0,y:.31,roll:2,size:.31},{x:.33,y:.27,roll:4,size:.31}];
const MEDIUM:PoolHome[]=[{x:-.235,y:.11,roll:-3,size:.42},{x:.235,y:.125,roll:3,size:.42},{x:-.235,y:.35,roll:3,size:.42},{x:.235,y:.36,roll:-3,size:.42}];
// On a phone the tray is taller than the screen: two rows of two, each print nearly half the width.
const TALL:PoolHome[]=[{x:-.245,y:.035,roll:-2,size:.45},{x:.245,y:.042,roll:2,size:.45},{x:-.245,y:.33,roll:2,size:.45},{x:.245,y:.337,roll:-2,size:.45}];
/** The headline owns the upper left on wide stages and the top on narrow ones; prints rest clear of it. */
export function poolHomes(aspect:number):PoolHome[]{return aspect>=1.25?WIDE:aspect>=.8?MEDIUM:TALL;}
/** Where the safelight hangs, below the header, in stage fractions from the top left. The shader, the fixture and the lit prints share it. */
export function safelight(aspect:number){return aspect>=.8?{x:.775,y:.09}:{x:.84,y:.085};}
/** Drift a visitor can see: a few percent of the tray each way, from incommensurate sines so a print never visibly repeats its path. */
export function driftOffset(index:number,time:number){return {x:Math.sin(time*.21+index*2.4)*.028+Math.sin(time*.097+index*5.1)*.014,y:Math.sin(time*.17+index*1.9)*.03+Math.sin(time*.083+index*3.7)*.014,roll:Math.sin(time*.15+index*1.3)*2.4+Math.sin(time*.061+index*4.2)*1.1};}
/** A region prints must not cover, in pixels from the tray's centre. */
export type Box={left:number;top:number;right:number;bottom:number};
/** Moves a print's centre the shortest way out of a region at the tray's upper left: to the right of it or below it. */
export function keepClear(x:number,y:number,halfWidth:number,halfHeight:number,box:Box|null){
 if(!box||x-halfWidth>=box.right||y-halfHeight>=box.bottom||x+halfWidth<=box.left||y+halfHeight<=box.top)return {x,y};
 const right=box.right+halfWidth-x,down=box.bottom+halfHeight-y;
 return right<=down?{x:x+right,y}:{x,y:y+down};
}
/** `lift` enlarges the print on the easel: its content is laid out at a comfortable design size and shown bigger. `clear` is the headline block a floating print stays out of. */
export function poolTarget(index:number,lifted:number|null,homes:PoolHome[],stageWidth:number,stageHeight:number,cardWidth:number,time:number,lift=1,clear:Box|null=null,cardHeight=0):CardPose{
 if(index===lifted)return {x:0,y:0,scale:lift,roll:0,pitch:0,alpha:1};
 const home=homes[index%homes.length],drift=driftOffset(index,time),scale=clamp(home.size*stageWidth/Math.max(1,cardWidth),.1,.7),waiting=lifted!==null;
 const roll=home.roll+drift.roll,turn=Math.abs(roll)*Math.PI/180,w=cardWidth*scale,h=cardHeight*scale;
 // The print's upright bounding box, turned as it is, stays out of the headline.
 const at=keepClear((home.x+drift.x)*stageWidth,(home.y+drift.y)*stageHeight,(w*Math.cos(turn)+h*Math.sin(turn))/2,(w*Math.sin(turn)+h*Math.cos(turn))/2,clear);
 // Scale stays fixed while a print floats: a changing scale makes the browser redraw the whole print every frame.
 return {x:at.x,y:at.y,scale,roll,pitch:0,alpha:waiting?.3:1};
}
/** How strongly a point is lit by a lamp, with distance measured in stage heights. */
export function lampFalloff(x:number,y:number,lampX:number,lampY:number,aspect:number,tightness:number){const dx=(x-lampX)*aspect,dy=y-lampY;return Math.exp(-(dx*dx+dy*dy)*tightness);}
