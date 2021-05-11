from brownie import accounts, interface, Contract
from brownie import (Bank, SimpleBankConfig, SimplePriceOracle, PancakeswapGoblin,
                     StrategyAllHTOnly, StrategyLiquidate, StrategyWithdrawMinimizeTrading, StrategyAddTwoSidesOptimal, PancakeswapGoblinConfig, TripleSlopeModel, ConfigurableInterestBankConfig, PancakeswapPool1Goblin, ProxyAdminImpl, TransparentUpgradeableProxyImpl)
from brownie import network
from .utils import *
from .constant import *
import eth_abi

# set default gas price
network.gas_price('1 gwei')

def test_token_1(bank, registry, token_name):
    alice = accounts.add('a8060afe2390bd0c00c7ef800f545d466b55cc84d4ad6d01e03220af03e97982')
    bob = accounts.add('7b9009958a83807bbe38bf35f451ff0c4bf4d926cee63dd07658762db58ceba4')


    # bank.deposit({'from': bob, 'value': '0.1 ether', 'gas_price':1000000000})

    prevBNBBal = alice.balance()

    bank.work(0, 
        registry[token_name]['goblin'], 
        10**17, 0, 
        eth_abi.encode_abi(
            ['address', 'bytes'], 
            [
                registry[token_name]['two_side'].address,
                eth_abi.encode_abi(['address', 'uint256', 'uint256'], [registry[token_name]['token'], 0, 0])
            ]
        ), {'from': alice, 'value': '0.05 ether', 'gas_price':1000000000})

    curBNBBal = alice.balance()

    print('∆ ht alice', curBNBBal - prevBNBBal)

    pos_id = bank.nextPositionID() - 1
    print('alice pos', bank.positionInfo(pos_id))


def test_token(bank, registry, add_strat, liq_strat, rem_strat, token_name):
    print('================================================')
    print('Testing', token_name)

    alice = accounts.add('a8060afe2390bd0c00c7ef800f545d466b55cc84d4ad6d01e03220af03e97982')
    bob = accounts.add('7b9009958a83807bbe38bf35f451ff0c4bf4d926cee63dd07658762db58ceba4')

    goblin = registry[token_name]['goblin']
    fToken = registry[token_name]['token']
    add_strat_2 = registry[token_name]['two_side']

    print('goblin', goblin)
    print('fToken', fToken)
    print('add_strat_2', add_strat_2)

    bank.deposit({'from': bob, 'value': '0.1 ether', 'gas_price':1000000000})

    prevBNBBal = alice.balance()

    bank.work(0, goblin, 10**17, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat_2.address,
                                                                              eth_abi.encode_abi(['address', 'uint256', 'uint256'], [fToken, 0, 0])]), {'from': alice, 'value': '0.05 ether', 'gas_price':1000000000})

    curBNBBal = alice.balance()

    print('∆ ht alice', curBNBBal - prevBNBBal)

    pos_id = bank.nextPositionID() - 1
    print('alice pos', bank.positionInfo(pos_id))

    assert almostEqual(curBNBBal - prevBNBBal, -10**17), 'incorrect BNB input amount'

    prevBNBBal = alice.balance()

    bank.work(pos_id, goblin, 0, 2**256-1, eth_abi.encode_abi(['address', 'bytes'], [
              liq_strat.address, eth_abi.encode_abi(['address', 'uint256'], [fToken, 0])]), {'from': alice, 'gas_price':1000000000})

    curBNBBal = alice.balance()

    print('∆ ht alice', curBNBBal - prevBNBBal)
    print('alice pos', bank.positionInfo(pos_id))

    if token_name == 'sashimi':
        bank.work(0, goblin, 10*17, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat_2.address,
                                                                                  eth_abi.encode_abi(['address', 'uint256', 'uint256'], [fToken, 0, 0])]), {'from': alice, 'value': '0.05 ether', 'gas_price':1000000000})
    else:
        bank.work(0, goblin, 10**17, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat.address,
                                                                                  eth_abi.encode_abi(['address', 'uint256'], [fToken, 0])]), {'from': alice, 'value': '0.05 ether', 'gas_price':1000000000})

    pos_id = bank.nextPositionID() - 1

    bank.work(pos_id, goblin, 0, 2**256-1, eth_abi.encode_abi(['address', 'bytes'], [
              rem_strat.address, eth_abi.encode_abi(['address', 'uint256'], [fToken, 0])]), {'from': alice, 'gas_price':1000000000})

    print('reinvesting')
    goblin.reinvest({'from': alice})

    print('liquidating')
    bank.work(0, goblin, 10**17, 0, eth_abi.encode_abi(['address', 'bytes'], [add_strat_2.address,
                                                                              eth_abi.encode_abi(['address', 'uint256', 'uint256'], [fToken, 0, 0])]), {'from': alice, 'value': '0.05 ether', 'gas_price':1000000000})

    pos_id = bank.nextPositionID() - 1

    pre_bank_bal = bank.balance()

    goblin.liquidate(pos_id, {'from': bank, 'gas_price': 0})

    post_bank_bal = bank.balance()

    print('liq gain', post_bank_bal - pre_bank_bal)
    assert post_bank_bal - pre_bank_bal > 0, 'liq gets 0'


def main():
    # deployer = accounts[0]
    # deployer = accounts.at('0x1dcEf12e93b0aBF2d36f723e8B59Cc762775d513', force=True)
    deployer = accounts.add('eb555556ca1b0a95142fa46019afa8451eb247dee035992742d60aa44316252f')
    alice = accounts.add('a8060afe2390bd0c00c7ef800f545d466b55cc84d4ad6d01e03220af03e97982')
    bob = accounts.add('7b9009958a83807bbe38bf35f451ff0c4bf4d926cee63dd07658762db58ceba4')

    # =====开始：重新部署合约===============================
    # print('1 部署 银行配置合约...')

    # print('  部署3段式利率模型 triple_slope_model...')
    # triple_slope_model = TripleSlopeModel.deploy({'from': deployer})

    # print('  部署可配银行配置合约 ConfigurableInterestBankConfig...')
    # print('  min debt 0.2 HT at 10 gwei gas price (avg gas fee = ~0.006 HT) (killBps 1% -> at least 0.01BNB bonus)')
    # print('  reserve pool bps 2000 (20%)')
    # print('  kill bps 100 (1%)')
    # bank_config = ConfigurableInterestBankConfig.deploy(
    #     2 * 10*17, 2000, 100, triple_slope_model, {'from': deployer})
    
    # print('2 部署 银行合约...')
    # print('  部署 ProxyAdminImpl...')
    # proxy_admin = ProxyAdminImpl.deploy({'from': deployer})
    # print('  部署 Bank...')
    # bank_impl = Bank.deploy({'from': deployer})
    # print('  部署 TransparentUpgradeableProxyImpl...')
    # bank = TransparentUpgradeableProxyImpl.deploy(
    #     bank_impl, proxy_admin, bank_impl.initialize.encode_input(bank_config), {'from': deployer})
    # bank = interface.IAny(bank)
    # print('3 部署 测试用的预言机合约...')
    # print('  部署 SimplePriceOracle...')
    # # oracle = SimplePriceOracle.deploy({'from': deployer})
    # oracle = SimplePriceOracle.at('0xf3e2206a87014A3acE8def4Bd65BE84CC9B2b388')

    # # strats
    # print('4 部署 策略合约...')
    # print('  部署 StrategyAllHTOnly... router_address =',router_address)
    # add_strat = StrategyAllHTOnly.deploy(router_address, {'from': deployer})
    # print('  部署流动性策略 StrategyLiquidate...')
    # liq_strat = StrategyLiquidate.deploy(router_address, {'from': deployer})
    # print('  部署提款策略 StrategyWithdrawMinimizeTrading...')
    # rem_strat = StrategyWithdrawMinimizeTrading.deploy(router_address, {'from': deployer})
    # print('  部署goblin的配置，传入oracle合约地址 PancakeswapGoblinConfig...')
    # goblin_config = PancakeswapGoblinConfig.deploy(oracle, {'from': deployer})
    # =====结束：重新部署合约===============================
    # ====================================
    # 或者关联到已部署合约
    bank_config = ConfigurableInterestBankConfig.at('0x50D73FF608c6a66b1c36f4a051363cC8a359621d')
    bank = TransparentUpgradeableProxyImpl.at('0xF1FB892E5072cE129Af13a795f211598A8931132')
    bank = interface.IAny(bank)
    oracle = SimplePriceOracle.at('0xf3e2206a87014A3acE8def4Bd65BE84CC9B2b388')
    add_strat = StrategyAllHTOnly.at('0x7Bc24bB9da86C808cf8cBC9ED935AC61068FCD34')
    liq_strat = StrategyLiquidate.at('0x04492d6C6bB5439e5916CC792b570DEd6a3563f6')
    rem_strat = StrategyWithdrawMinimizeTrading.at('0x5158e8E7a7C45050Cd039802530473b01570f1f2')
    goblin_config = PancakeswapGoblinConfig.at('0x21952994097720Db2356B73617F7d03ee9662Eaa')
    # ====================================

    print('  部署后合约地址汇总：')
    print('  bank', bank.address)
    print('  bank_config', bank_config.address)
    print('  all ht', add_strat.address)
    print('  liq', liq_strat.address)
    print('  withdraw', rem_strat.address)
    print('  goblin_config', goblin_config.address)
    

    pools = [
        {
            'name': 'sashimi',
            'token': sashimi_address,
            'lp': sashimi_lp_address,
            'pid': 1,
            'goblinConfig': [True, 6250, 7000, 11000]
        }
        ]

    wht = interface.IAny(wht_address)
    print(' WHT的地址是:', wht_address)
    # =====开始：重新配置交易池===============================
    # registry = {}
    # print('5 部署交易池...')
    # for pool in pools:
    #     print('  ==============================')
    #     print('  部署交易对：wht -'，pool['name'],'地址是：',pool['token'])
    #     fToken = interface.IAny(pool['token'])

    #     if pool['pid'] == 1:
    #         # reinvest 0.3% (avg gas fee ~0.006 BNB)
    #         print('  部署 pid=1 的交易对的gobilin PancakeswapPool1Goblin ... reinvest 0.3%')
    #         goblin = PancakeswapPool1Goblin.deploy(
    #                     ank, 
    #                     chef_address, 
    #                     router_address, 
    #                     add_strat, 
    #                     liq_strat, 
    #                     30, 
    #                     {'from': deployer})
    #     else:
    #         # reinvest 0.3% (avg gas fee ~0.006 BNB)
    #         print('  部署 pid>1 的交易对的gobilin PancakeswapGoblin ... reinvest 0.3%')
    #         goblin = PancakeswapGoblin.deploy(
    #                     bank, 
    #                     chef_address, 
    #                     router_address, 
    #                     pool['pid'], 
    #                     add_strat, 
    #                     liq_strat, 
    #                     30, 
    #                     {'from': deployer})
    #     print('  配置goblin的配置数据到配置合约中 goblin_config.setConfigs ...',pool['goblinConfig'])
    #     goblin_config.setConfigs([goblin], [pool['goblinConfig']], {'from': deployer})
        
    #     print('  部署双边策略合约：add_strat_2 StrategyAddTwoSidesOptimal ...')
    #     add_strat_2 = StrategyAddTwoSidesOptimal.deploy(
    #         router_address, goblin, fToken, {'from': deployer})
    #     print('  配置双边策略add_strat_2到 goblin goblin.setStrategyOk ...')
    #     goblin.setStrategyOk([add_strat_2, rem_strat], True, {'from': deployer})
    #     print('  配置goblin到银行配置合约 bank_config.setGoblins ...')
    #     bank_config.setGoblins([goblin], [goblin_config], {'from': deployer})

    #     # re-assign two side strat as add strat for pool 1 goblin
    #     if pool['pid'] == 1:
    #        print('  对于pid=1的交易池 配置更严格的策略add_strat_2到goblin ...')
    #         goblin.setCriticalStrategies(add_strat_2, liq_strat, {'from': deployer})
    #         print(' 配置add_strat到goblin goblin.setStrategyOk ...')
    #         goblin.setStrategyOk([add_strat], False, {'from': deployer})  # unset add_strat

    #     registry[pool['name']] = {'goblin': goblin,
    #                               'two_side': add_strat_2, 
    #                               'token': fToken.address}
    #     print('  交易池配置完成！！ registry[',pool["name"],']:',registry[pool['name']])
    # =====结束：重新配置交易池===============================

    # 或者使用已部署的池子
    registry = {}
    goblin = PancakeswapPool1Goblin.at('0xB67e7267fc3180679AC2C4A0C13442C15321670D')
    add_strat_2 = StrategyAddTwoSidesOptimal.at('0xe00ff084fe9d67CA6736052aFeb00F2870315F91')
    
    registry['sashimi'] = {'goblin': goblin,
                           'two_side': add_strat_2, 
                           'token': '0xc2037C1c13dd589e0c14C699DD2498227d2172cC'}
    print('registry[ sashimi ]:',registry['sashimi'])
    # ====================================

    wht = interface.IAny(wht_address)
    sashimi = interface.IAny(sashimi_address)
    lp = interface.IAny(sashimi_lp_address)
    r0, r1, _ = lp.getReserves()
    sashimi_price = r1 * 10**18 // r0  # in bnb
    oracle.setPrices([sashimi], [wht], [sashimi_price], {'from': deployer})
    print('6 配置交易对的价格 sashimi对wht的价格的价格是',sashimi_price / 10**18)
    print('  lptoken 总供应量是：',lp.totalSupply() / 10**18)
    print('  当前bank存款：',bank.totalSupply() / 10**18)
    
    # set whitelist tokens to add_strat (no sashimi)
    add_fTokens = list(map(lambda pool: pool['token'], pools[1:]))
    print('add_fTokens:', add_fTokens)
    print('add_strat.setWhitelistTokens ...')
    add_strat.setWhitelistTokens(add_fTokens, [True] * len(add_fTokens), {'from': deployer, 'gas_price':1000000000})

    # set whitelist tokens to liq_strat, rem_strat
    fTokens = list(map(lambda pool: pool['token'], pools))
    print('fTokens:', fTokens)
    print('liq_strat.setWhitelistTokens ...')
    liq_strat.setWhitelistTokens(fTokens, [True] * len(fTokens), {'from': deployer})
    print('rem_strat.setWhitelistTokens ...')
    rem_strat.setWhitelistTokens(fTokens, [True] * len(fTokens), {'from': deployer})
    # mint tokens
    # mint_tokens(sashimi, alice)
    # approve tokens
    sashimi.approve(add_strat_2, 2**256-1, {'from': alice})
    wht.approve(bank, 2**256-1, {'from': alice})
    #########################################################################
    # test work

    print('  开始测试token: sashimi ...')
    print('  bank.nextPositionID=',bank.nextPositionID())
    print('  接收债务吗? ',bank_config.acceptDebt(registry['sashimi']['goblin']))
    print('  minDebtSize= ',bank_config.minDebtSize())
    print('  minDebtSize.workFactor= ', bank_config.workFactor(registry['sashimi']['goblin'], bank_config.minDebtSize()))
    print('  workFactor= ', bank_config.workFactor(registry['sashimi']['goblin'], 10**17))
    
    # ========================
    prevBNBBal = alice.balance()
    bank.work(0, 
        registry['sashimi']['goblin'], 
        10**17, 0, 
        eth_abi.encode_abi(
            ['address', 'bytes'], 
            [
                registry['sashimi']['two_side'].address,
                eth_abi.encode_abi(['address', 'uint256', 'uint256'], [registry['sashimi']['token'], 0, 0])
            ]
        ), {'from': alice, 'value': '0.05 ether', 'gas_price':1000000000})
    curBNBBal = alice.balance()

    print('  bank.nextPositionID=',bank.nextPositionID())
    pos_id = bank.nextPositionID() - 1
    print('  goblin.health=',goblin.health(pos_id)) 
    print('  goblin.shares=',goblin.shares(pos_id))  
    print('  goblin.shareToBalance(goblin.shares)=',goblin.shareToBalance(goblin.shares(pos_id)))  

    print('  ∆ ht alice', curBNBBal - prevBNBBal)
    
    print('  alice pos', bank.positionInfo(pos_id))

    # print('测试token ...')
    # test_token(bank, registry, add_strat, liq_strat, rem_strat, 'sashimi')

