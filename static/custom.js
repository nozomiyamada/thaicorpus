////////////////////////////// GENERAL FUNCTION FOR ALL PAGES //////////////////////////////

function show_hide(targetID){
	let elem = document.getElementById(targetID);
	if(elem.style.display=='none'){
		$(elem).show('fast');
	}else{
		$(elem).hide('fast');
	}
}

////////////////////////////// FUNCTION FOR CORPUS //////////////////////////////



// make datalist for input
function make_list(n, present_input){
	// select datalist for input1 or 2 
	let datalist = (n==1)? datalist1 : datalist2;
	datalist.innerHTML = ""; // initialize
	// get present input
	if(present_input.length >= 3){
		var num_candidate = 0; 
		for(var vocab of VOCABS){ // VOCABS is in vocab.js
			if(vocab.startsWith(present_input)){
				datalist.innerHTML += `<option value="${vocab}">${vocab}</option>`;
				num_candidate += 1;
				if(num_candidate >= 6){break;} // show only 6 candidates
			}
		}
	}
}

// COOKIE
function set_history(){
	let histories = document.cookie.match(/history\d\d?=/g); // history0 ~ history10 (max)
	history_num = (histories == null)? 0 : histories.length;
	if(history_num !== 0){
		history_table.innerHTML = ""; // initialize history table
		for(var i=0; i<history_num; i++){
			// get sent data as dict : "{"mode":"word","sources":["source_twitter","source_matichon"],"input1":"อาหาร","input2":"","input3":"",
			// "n_left":"1","n_right":"1","use_multiple_words":false,"is_regex":false,"media":"PC"}"
			dic = JSON.parse(Cookies.get(`history${i}`)); 
			if(dic.mode=="word"){
				history_table.innerHTML +=
				`<tr>
					<td class="history">
					${(dic.input_word1 + " " + dic.input_word2).trim()}</td>
					<td class="table-danger">SEARCH BY WORD</td>
				</tr>`;
			}else if(dic.mode=='string'){
				history_table.innerHTML +=
				`<tr>
					<td class="history">
					${(dic.input_string1 + " " + dic.input_string2).trim()}</td>
					<td class="table-primary">SEARCH BY STRING</td>
				</tr>`;
			}
		}
	}
}


////////// Press Enter Key to search //////////
document.addEventListener('keyup', function(event){
	if(event.keyCode == '13'){
		if(['input_word1', 'input_word2'].includes(document.activeElement.id)){
			start_ajax('word');
		}else if(['input_string1', 'input_string2'].includes(document.activeElement.id)){
			start_ajax('string');
		}
	}
});



////////////////////////////// SHOW RESULT: SEARCH BY WORD //////////////////////////////

function show_result_word(data){
	////////// get chart element //////////
	//console.log(data)
	word_freq_canvas.style.display = ""; // make chart visible
	var chartChart = document.getElementById("wf_chart");
	////////// make dataset //////////
	var word_freq1 = data.word_freq1; // receive word freq & search time as array: [[source, wf, time],...]
	var query1 = vue.input_word1;
	if(data.is_oneword){
		var dataset = [{label: `${query1}`, data: word_freq1.map(x => x[1]), backgroundColor: "#75baff"}];
	}else{
		var word_freq2 = data.word_freq2; 
		var query2 = vue.input_word2;
		var dataset = [
			{label: `${query1}`, data: word_freq1.map(x => x[1]), backgroundColor: "#75baff"},
			{label: `${query2}`, data: word_freq2.map(x => x[1]), backgroundColor: "#ff8ce8"}
		];
	}

	////////// draw chart //////////
	
	new Chart(chartChart, {
		type: "bar",
		data: {
			labels: word_freq1.map(x => x[0] + ` (${x[2]}sec)`), // twitter (12sec)
			datasets: dataset
		},
		options: {
			responsive: true,
			title: {
				display: true,
				text: "word frequecy / 1M words (fetch time)"
			},
			scales: {
				yAxes: [{
					ticks: {
						beginAtZero:true
					}
				}]
			}
		}
	});

	///////// create ngram table //////////
	if(data.is_oneword){ // search by only one word
		vue.result_word = 1;
		table_oneword.innerHTML = ""; // initinalize table 
		for(i=0; i<data.ngrams1.length; i++){ // ngrams1 = [[ngramL, count, ngramR, count],...]
			ngramL = data.ngrams1[i][0].replace(/</g, "&lt;").replace(/>/g, "&gt;"); // replave < > with &lt; &gt;
			countL = data.ngrams1[i][1];
			ngramR = data.ngrams1[i][2].replace(/</g, "&lt;").replace(/>/g, "&gt;");
			countR = data.ngrams1[i][3];
			// show popover to continue to search word/string 
			table_oneword.innerHTML += `
			<tr class="table">
				<td class="center ngramL">
					<span tabindex="-1"  data-trigger="focus" class="pointer"data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramL.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramL.replace(/ /g,'').replace(/\|/g,'').replace(/__/g,' ')}</span>'>
						${ngramL}
					</span>
				</td> 
				<td class="center ngramL2">${countL}</td>
				<td class="center ngramR">
					<span tabindex="-1"  data-trigger="focus" class="pointer" data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramR.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramR.replace(/ /g,'').replace(/\|/g,'').replace(/__/g,' ')}</span>'>
						${ngramR}
					</span>
				</td>
				<td class="center ngramR2">${countR}</td>
			</tr>`;
		}
	
	}else if(data.is_twoword){// search by two words
		vue.result_word = 2;
		table_twoword1.innerHTML = ""; // initinalize table 
		table_twoword2.innerHTML = "";
		for(i=0; i<data.ngrams1.length; i++){
			ngramL = data.ngrams1[i][0].replace(/</g, "&lt;").replace(/>/g, "&gt;"); // replave < > with &lt; &gt;
			countL = data.ngrams1[i][1];
			ngramR = data.ngrams1[i][2].replace(/</g, "&lt;").replace(/>/g, "&gt;");
			countR = data.ngrams1[i][3];
			// show popover to continue to search word/string 
			table_twoword1.innerHTML += `
			<tr class="table">
				<td class="center ngramL">
					<span tabindex="-1"  data-trigger="focus" class="pointer"data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramL.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramL.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramL}
					</span>
				</td> 
				<td class="center ngramL2">${countL}</td>
				<td class="center ngramR">
					<span tabindex="-1"  data-trigger="focus" class="pointer" data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramR.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramR.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramR}
					</span>
				</td>
				<td class="center ngramR2">${countR}</td>
			</tr>`;
		}
		for(i=0; i<data.ngrams2.length; i++){
			ngramL = data.ngrams2[i][0].replace(/</g, "&lt;").replace(/>/g, "&gt;"); // replave < > with &lt; &gt;
			countL = data.ngrams2[i][1];
			ngramR = data.ngrams2[i][2].replace(/</g, "&lt;").replace(/>/g, "&gt;");
			countR = data.ngrams2[i][3];
			// show popover to continue to search word/string 
			table_twoword2.innerHTML += `
			<tr class="table">
				<td class="center ngramL">
					<span tabindex="-1"  data-trigger="focus" class="pointer"data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramL.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramL.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramL}
					</span>
				</td> 
				<td class="center ngramL2">${countL}</td>
				<td class="center ngramR">
					<span tabindex="-1"  data-trigger="focus" class="pointer" data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramR.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramR.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramR}
					</span>
				</td>
				<td class="center ngramR2">${countR}</td>
			</tr>`;
		}
	}
	$('body [data-toggle="popover"]').popover({html:true, sanitize: false}); // reactivate popovers, sanitize=false because embbed html in popover
}



////////////////////////////// SHOW RESULT: SEARCH BY STRING //////////////////////////////

function show_result_string(data, mode){
	if(data.is_oneword){ // search by only one string
		vue.result_string = 1;
		result_onestring_num.innerText = data.results1.length; // number of records
		table_onestring.innerHTML = ""; // initinalize table
		(data.results1.length > 20)? btn_show_more0.style.display = "" : btn_show_more0.style.display = "none"; // show more button
		for(i=0; i<data.results1.length; i++){
			if(i<20){
				table_onestring.innerHTML +=
				`<tr class="table">
					<td class="center">${data.results1[i][0]}</td> 
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}else{
				table_onestring.innerHTML +=
				`<tr class="table hidden_result0">
					<td class="center">${data.results1[i][0]}</td>
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}
		}
		
	}else{ // search by two strings
		vue.result_string = 2;
		result_twostring_num1.innerText = data.results1.length;
		result_twostring_num2.innerText = data.results2.length;
		table_twostring1.innerHTML = ""; // initinalize table
		table_twostring2.innerHTML = "";
		btn_show_more1.style.display = (data.results1.length > 20)?  "" : "none";
		btn_show_more2.style.display = (data.results2.length > 20)?  "" : "none";
		for(i=0; i<data.results1.length; i++){
			if(i<20){
				table_twostring1.innerHTML +=
				`<tr class="table">
					<td class="center">${data.results1[i][0]}</td>
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}else{
				table_twostring1.innerHTML +=
				`<tr class="table hidden_result1">
					<td class="center">${data.results1[i][0]}</td>
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}
		}
		for(i=0; i<data.results2.length; i++){
			if(i<20){
				table_twostring2.innerHTML +=
				`<tr class="table">
					<td class="center">${data.results2[i][0]}</td>
					<td class="center">${data.results2[i][1]}</td>
				</tr>`;
			}else{
				table_twostring2.innerHTML +=
				`<tr class="table hidden_result2">
					<td class="center">${data.results2[i][0]}</td>
					<td class="center">${data.results2[i][1]}</td>
				</tr>`;
			}
		}
	}
}

function show_more(n){
	event.target.blur(); // unforcus button
	current_X = window.scrollX;
	current_Y = window.scrollY;
	let hidden = document.getElementsByClassName(`hidden_result${n}`); // get hidden <tr>
	if(hidden.length<=20){
		document.getElementById(`btn_show_more${n}`).style.display = "none";
	}
	Array.from(hidden).slice(0,20).forEach(x => x.classList.remove(`hidden_result${n}`));
	// scroll to original position
	window.scrollTo(current_X, current_Y);
}
