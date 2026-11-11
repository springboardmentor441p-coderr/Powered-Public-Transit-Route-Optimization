// Render with pptxgenjs installed locally; no input data is downloaded or changed.
const fs = require('fs');
const path = require('path');
const PptxGenJS = require('pptxgenjs');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'handoff', 'final');
const evidence = JSON.parse(fs.readFileSync(path.join(output, 'presentation_inputs.json'), 'utf8'));
const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'RouteRanker'; pptx.subject = 'Historical transit planning prototype';
pptx.title = 'RouteRanker: from observed demand to review proposals';
pptx.lang = 'en-US'; pptx.theme = {headFontFace:'Arial',bodyFontFace:'Arial',lang:'en-US'};
const C={navy:'183B56',teal:'087F8C',orange:'D17A30',light:'EDF2F7',white:'FFFFFF',grey:'52697D'};
function text(s,t,x,y,w,h,size=18,color=C.navy,bold=false){
 s.addText(t,{x,y,w,h,fontFace:'Arial',fontSize:size,color,bold,margin:0,breakLine:false, valign:'mid'});
}
function slide(title,subtitle=''){
 const s=pptx.addSlide();s.background={color:C.white};
 text(s,title,.65,.45,12,1.05,34,C.navy,true);
 if(subtitle) text(s,subtitle,.65,1.52,12,.55,15,C.grey);
 text(s,'RouteRanker | Manhattan planning study | 8 November 2026',.65,7.04,11,.2,9,C.grey);
 text(s,String(pptx._slides.length),12.1,7.02,.5,.24,10,C.grey);
 return s;
}
function card(s,x,y,w,h,title,body,titleSize=23){
 s.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:.15,line:{color:C.light},fill:{color:C.light},radius:.15});
 text(s,title,x+.23,y+.2,w-.46,.55,titleSize,C.teal,true);
 text(s,body,x+.23,y+.95,w-.46,h-1.15,17,C.navy);
}
function chart(s,labels,values,title,yTitle,y=2.35){
 s.addChart(pptx.ChartType.bar,[{name:title,labels,values}],{x:.8,y,w:11.7,h:3.8,
  catAxisLabelFontFace:'Arial',catAxisLabelFontSize:13,valAxisLabelFontSize:11,
  showTitle:true,title,titleFontFace:'Arial',titleFontSize:18,showLegend:false,
  showValue:true,dataLabelPosition:'outEnd',dataLabelFormatCode:'#,##0.00',
  chartColors:[C.teal],catAxisLabelColor:C.navy,valAxisLabelColor:C.grey,
  valAxisTitle:yTitle,showCatName:false,showBorder:false,
  valGridLine:{color:'DCE5EE',size:1},catGridLine:{style:'none'},
  showCatName:false,catAxisTitle:'',valAxisMinVal:0});
}
let s=pptx.addSlide();
s.background={color:C.navy};
// Recolor title/subtitle on the dark title slide.
text(s,'RouteRanker',.8,.7,11,1,46,C.white,true);
text(s,'Observed demand. Matched service. Explicit alternatives.',.8,1.85,11,1,27,'92D8D9');
card(s,.8,3.25,3.7,2.4,'41 routes','Manhattan study with versioned historical inputs');
card(s,4.8,3.25,3.7,2.4,'78 shared dates','Common observation window for route review');
card(s,8.8,3.25,3.7,2.4,'Planner review','Evidence and scenarios; operational validation remains separate');
s.addNotes('Scope: historical planning prototype. The study does not cover 23 Indian cities. No measured crowding or intervention benefit is claimed.');
s=slide('A planner task, end to end','Prepare a review proposal before making an operational service decision.');
card(s,.75,2.3,3.75,3.8,'1. Investigate','Select a route and period. Inspect observed demand, matching schedules, quality flags and peer coverage.');
card(s,4.8,2.3,3.75,3.8,'2. Compare','Inspect review reasons. Compare frequency alternatives or an explicit added-hour allocation.');
card(s,8.85,2.3,3.75,3.8,'3. Retain evidence','Save assumptions, baseline identifiers, required checks and scenario outputs for a planning meeting.');
s=slide('A traceable analytical foundation','Original observations remain separate from schedules, forecasts and assumptions.');
card(s,.8,2.2,5.7,1.65,'10,014 route/dates','Eligible historical daily demand/service comparisons');
card(s,6.8,2.2,5.7,1.65,'5 historical archives','Whole-feed date selection with calendar exceptions');
card(s,.8,4.2,5.7,1.65,'27 pinned dashboard inputs','Fingerprint checks before analytical display');
card(s,6.8,4.2,5.7,1.65,'Real import verified','1,174,914 stop events; 8,575 active bus templates on 14 September');
s.addNotes('Source: matched_daily_features.csv, dashboard_data_manifest.json, reports/completion/real_gtfs_import_audit.json. Boarding estimates are entries, not on-board loads.');
s=slide('Forecasts: compare against a credible baseline','574 additional October route/date targets; retrospective assessment, not operational acceptance.');
chart(s,['Seasonal reference','Anchored challenger'],[669.3449477352,631.8329871067],'Mean absolute error','Daily boardings');
text(s,'5.60% lower MAE for the earlier-selected challenger. Its empirical ranges remain withheld.',.9,6.35,11.6,.45,16,C.navy);
s.addNotes('Source: october_validation/additional_october_scores.csv. Dates 1-4 and 12-21 October. Challenger range coverage fails the declared screen. Prospective acceptance remains pending.');
s=slide('Review evidence without invented performance labels','Named indicators, sample sizes, periods, source issues and sensitivity remain visible.');
card(s,.8,2.25,3.7,2.8,'22 routes','Planning review signals; investigate the evidence before proposing changes.');
card(s,4.8,2.25,3.7,2.8,'18 routes','No triggered rule; this does not establish balanced or efficient service.');
card(s,8.8,2.25,3.7,2.8,'M98 withheld','Four positive-boardings / zero-scheduled-service dates require source clarification.');
text(s,'Merge/split hypotheses remain provisional until stop order, access, journeys and resources are checked.',.9,5.65,11.6,.8,20,C.navy);
s=slide('A constrained service-allocation experiment','Weekdays: 50 added scheduled bus-hours, 20% route cap, no cuts, 40 eligible routes.');
const a=evidence.allocation;
chart(s,['Baseline','Equal-spend uniform','Constrained allocation'],[a.baseline_objective/1e6,a.equal_spend_uniform_objective/1e6,a.allocation_objective/1e6],'Boarding-intensity concentration proxy','Proxy value, millions');
text(s,'2.18% proxy reduction. This does not measure crowding, waiting time or passenger benefit.',.9,6.35,11.6,.45,16,C.navy);
s.addNotes('Objective: minimize sum D squared / N, fixed historical demand, proportional scheduled-hour scaling, continuous daily means. Source: reports/completion/allocation_summary.json. No executable timetable is generated.');
s=slide('The application and handoff','Streamlit is the application interface; datasets and private files remain outside public code.');
card(s,.8,2.2,5.7,3.6,'Delivered workflows','Routes and comparison\nReview evidence and forecasts\nFrequency scenarios and allocation\nValidated GTFS intake\nSaved proposal packages');
card(s,6.8,2.2,5.7,3.6,'Reproducible package','Executed analytical notebooks\nTested shared calculations\nTechnical report and architecture\nDemo and deployment instructions\nContainer configuration');
text(s,'Container execution still requires verification on a Docker-equipped host.',.9,6.15,11.5,.5,16,C.grey);
s=slide('What is still required for operational claims','The next evidence is more valuable than another chart.');
card(s,.8,2.2,3.7,3.8,'Observed loads','Independent overcrowding assessments and capacity evidence. The classifier workflow is ready; real labels are not installed.');
card(s,4.8,2.2,3.7,3.8,'Feasible changes','Direction/time-specific journeys, coverage, fleet, staffing and an executable timetable.');
card(s,8.8,2.2,3.7,3.8,'Prospective checks','Mature issued forecasts, publication vintages, operational approval and outcome evaluation.',19);
s.addNotes('The implementation remains New York-specific. It does not claim fulfillment of the 23-Indian-city geography. Source and feasibility gaps are explicitly retained in documentation/DELIVERY_STATUS.md.');
pptx.writeFile({fileName:path.join(output,'RouteRanker_Stakeholder_Presentation.pptx')});
