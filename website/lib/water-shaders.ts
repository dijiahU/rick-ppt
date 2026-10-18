export const WATER_VERTEX=`
attribute vec2 aPosition;
varying vec2 vUv;
void main(){vUv=aPosition*.5+.5;gl_Position=vec4(aPosition,0.,1.);}
`;
export const WATER_FRAGMENT=`
precision highp float;
varying vec2 vUv;
uniform vec2 uResolution;
uniform vec2 uTexel;
uniform float uTime;
uniform sampler2D uHeight;
uniform sampler2D uEnvironment;
uniform vec4 uSurges[6];
uniform vec4 uCards[3];
const float PI=3.14159265;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);}
float readHeight(vec2 p){vec2 rg=texture2D(uHeight,clamp(p,.001,.999)).rg;return ((rg.x*256.+rg.y)/257.-.5)*6.;}
// One travelling swell with aligned harmonics: soft parallel crests, no crossing lattice.
float swellPhase(vec2 p){return p.y*6.4+sin(p.x*1.05+uTime*.05)*.55+sin(p.x*2.8-uTime*.08)*.18-uTime*.88;}
float smallWaves(vec2 p){float phase=swellPhase(p);float amplitude=.82+.18*noise(vec2(p.x*1.4,p.y*.3));return (sin(phase)*.055+sin(phase*2.+.35)*.009+sin(phase*3.+sin(p.x*2.)*.4)*.0035)*amplitude;}
// Approximate sunlight focusing from the curvature of smooth travelling waves.
// The ray-map Jacobian produces continuous curved folds rather than cell borders.
float poolCaustics(vec2 p){
 float t=uTime*.44;
 vec2 k0=vec2(2.8,1.2),k1=vec2(-1.6,3.1),k2=vec2(3.6,-2.3),k3=vec2(.7,4.5);
 float h0=-.095*sin(dot(p,k0)-t);
 float h1=-.075*sin(dot(p,k1)+t*.83+1.9);
 float h2=-.034*sin(dot(p,k2)-t*1.17+3.7);
 float h3=-.021*sin(dot(p,k3)+t*.67+.8);
 float xx=h0*k0.x*k0.x+h1*k1.x*k1.x+h2*k2.x*k2.x+h3*k3.x*k3.x;
 float yy=h0*k0.y*k0.y+h1*k1.y*k1.y+h2*k2.y*k2.y+h3*k3.y*k3.y;
 float xy=h0*k0.x*k0.y+h1*k1.x*k1.y+h2*k2.x*k2.y+h3*k3.x*k3.y;
 float determinant=(1.+xx*1.25)*(1.+yy*1.25)-xy*xy*1.5625;
 float focus=exp(-determinant*determinant*36.);
 float glow=exp(-abs(determinant)*2.1);
 float concentration=.65+.35*noise(p*1.7+vec2(t*.16,-t*.09));
 return (focus*.74+glow*.26)*concentration;
}
vec3 environment(vec3 ray){vec2 e=vec2(atan(ray.z,ray.x)/(2.*PI)+.5,acos(clamp(ray.y,-1.,1.))/PI);e.y=min(e.y,.38);return texture2D(uEnvironment,e).rgb;}
void main(){
 vec2 uv=vUv;vec2 topUv=vec2(uv.x,1.-uv.y);float aspect=uResolution.x/uResolution.y;
 // A shallow perspective plane. The simulated field remains in screen coordinates
 // so a pointer disturbance and its floating paper share the same place.
 float perspective=1./(.55+topUv.y*1.15);
 vec2 p=vec2((uv.x-.5)*aspect*4.,3.2)*perspective;
 p*=max(1.,1.2/aspect);
 float h=readHeight(topUv);float dx=(readHeight(topUv+vec2(uTexel.x,0))-readHeight(topUv-vec2(uTexel.x,0)))*.9;
 float dy=(readHeight(topUv+vec2(0,uTexel.y))-readHeight(topUv-vec2(0,uTexel.y)))*.9;
 float e=.035;dx+=(smallWaves(p+vec2(e,0))-smallWaves(p-vec2(e,0)))/(2.*e)*.42;dy+=(smallWaves(p+vec2(0,e))-smallWaves(p-vec2(0,e)))/(2.*e)*.42;
 float foam=0.;
 for(int i=0;i<6;i++){vec4 wave=uSurges[i];float age=uTime-wave.x;if(age>=0.&&age<3.){float front=mix(-.18,1.18,age/2.15);if(wave.y<0.)front=1.-front;float curve=sin(topUv.y*5.5+wave.w)*.038;float distanceToFront=topUv.x-front+curve;float ridge=exp(-distanceToFront*distanceToFront/0.0016)*exp(-age*.65)*wave.z;dx+=ridge*.42*sin(distanceToFront*50.);dy+=ridge*.09*cos(topUv.y*5.5+wave.w);foam+=ridge*.18;}}
 vec3 normal=normalize(vec3(-dx*1.25,1.,dy*1.25));vec3 view=normalize(vec3((.5-uv.x)*.4,.86,.82+uv.y*.32));vec3 reflected=reflect(-view,normal);
 float fresnel=.025+.975*pow(1.-max(0.,dot(view,normal)),5.);
 vec2 refracted=p+normal.xz*.28;
 // A softly lit, pale developer bath keeps the ripples visible and the prints legible.
 float grain=(noise(refracted*30.)-.5)*.006+(noise(refracted*8.)-.5)*.009;
 float mottling=(noise(refracted*1.9)-.5)*.018;
 vec2 lampDelta=(topUv-vec2(.10,.18))*vec2(aspect,.85);
 float safelight=exp(-dot(lampDelta,lampDelta)*2.8);
 vec3 floorColor=mix(vec3(.42,.52,.50),vec3(.57,.65,.58),topUv.y);
 floorColor+=vec3(grain+mottling+smallWaves(p)*.05+clamp(h,-.3,.3)*.012);
 floorColor+=vec3(.045,.02,.008)*safelight;
 float bathLight=poolCaustics(refracted*1.5+vec2(.7,1.4));
 floorColor+=vec3(.14,.15,.105)*bathLight*.16;
 reflected.y=max(.04,reflected.y);
 float softbox=exp(-pow((reflected.x+.24)*3.2,2.)-pow((reflected.z-.72)*7.,2.));
 vec3 reflection=vec3(.40,.51,.49)+vec3(.28,.27,.22)*softbox+vec3(.045,.02,.008)*safelight;
 reflection+=environment(normalize(reflected))*.035;
 vec3 water=mix(floorColor,reflection,clamp(fresnel+.15,0.,.48));
 // Broad shading describes each small wave without a web of white highlights.
 water*=1.+clamp(normal.x*.035+normal.z*.10,-.055,.055);
 float crest=pow(max(0.,sin(swellPhase(p)-.25)),9.);
 float crestBreakup=.25+.75*noise(vec2(p.x*3.2-uTime*.045,p.y*.8));
 water=mix(water,vec3(.68,.77,.67),crest*crestBreakup*.05);
 vec3 light=normalize(vec3(-.35,1.,-.7));float spec=pow(max(0.,dot(reflect(-light,normal),view)),55.);
 float glint=pow(max(0.,dot(reflect(-normalize(vec3(.2,1.,-.95)),normal),view)),180.);
 water+=vec3(.66,.67,.48)*spec*.07+vec3(.87,.87,.68)*glint*.03;
 // Soft reflected paper silhouettes, refracted by the same water normal.
 for(int i=0;i<3;i++){vec4 card=uCards[i];vec2 q=abs(topUv-(card.xy+normal.xz*.028))-card.zw;float edge=length(max(q,0.))+min(max(q.x,q.y),0.);float reflectedPaper=exp(-max(edge,0.)*45.)*.045;water=mix(water,vec3(.65,.68,.54),reflectedPaper);}
 foam+=texture2D(uHeight,topUv).b*.035;water=mix(water,vec3(.69,.76,.61),clamp(foam*.6,0.,.16));
 float vignette=clamp(length((uv-.5)*vec2(1.,.7)),0.,1.);water*=1.-vignette*.05;
 // The tray's shaded rim contains the bath; the surrounding site stays ivory.
 float edgeFade=smoothstep(0.,.035,uv.y)*smoothstep(0.,.045,1.-uv.y);water=mix(vec3(.32,.41,.37),water,edgeFade);
 gl_FragColor=vec4(clamp(water,0.,1.),1.);
}
`;
