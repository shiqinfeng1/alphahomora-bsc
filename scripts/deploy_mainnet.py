from brownie import accounts, interface, Contract
from brownie import (Bank, SimpleBankConfig, SimplePriceOracle, PancakeswapGoblin,
                     StrategyAllHTOnly, StrategyLiquidate, StrategyWithdrawMinimizeTrading, StrategyAddTwoSidesOptimal, PancakeswapGoblinConfig, TripleSlopeModel, ConfigurableInterestBankConfig, PancakeswapPool1Goblin, ProxyAdminImpl, TransparentUpgradeableProxyImpl)
from brownie import network
from .utils import *
from .constant import *
import eth_abi

# set default gas price
network.gas_price('10 gwei')


def deploy(deployer):
    triple_slope_model = TripleSlopeModel.deploy({'from': deployer, 'gas_price':1000000000})

    # min debt 1 BNB at 10 gwei gas price (avg gas fee = ~0.006 BNB) (killBps 1% -> at least 0.01BNB bonus)
    # reserve pool bps 2000 (20%)
    # kill bps 100 (1%)
    print('部署 bank_config...')
    bank_config = ConfigurableInterestBankConfig.deploy(
        10*17, 2000, 100, triple_slope_model, {'from': deployer, 'gas_price':1000000000})
    print('部署 ProxyAdminImpl...')
    proxy_admin = ProxyAdminImpl.deploy({'from': deployer, 'gas_price':1000000000})
    print('部署 Bank...')
    bank_impl = Bank.deploy({'from': deployer, 'gas_price':1000000000})
    print('部署 TransparentUpgradeableProxyImpl...')
    bank = TransparentUpgradeableProxyImpl.deploy(
        bank_impl, proxy_admin, bank_impl.initialize.encode_input(bank_config), {'from': deployer, 'gas_price':1000000000})
    bank = interface.IAny(bank)
    print('部署 SimplePriceOracle...')
    # oracle = SimplePriceOracle.deploy({'from': deployer, 'gas_price':1000000000})
    oracle = SimplePriceOracle.at('0xf3e2206a87014A3acE8def4Bd65BE84CC9B2b388')

    # strats
    print('部署 StrategyAllHTOnly... router_address =',router_address)
    add_strat = StrategyAllHTOnly.deploy(router_address, {'from': deployer, 'gas_price':1000000000})
    print('部署 StrategyLiquidate...')
    liq_strat = StrategyLiquidate.deploy(router_address, {'from': deployer, 'gas_price':1000000000})
    print('部署 StrategyWithdrawMinimizeTrading...')
    rem_strat = StrategyWithdrawMinimizeTrading.deploy(router_address, {'from': deployer, 'gas_price':1000000000})
    print('部署 PancakeswapGoblinConfig...')
    goblin_config = PancakeswapGoblinConfig.deploy(oracle, {'from': deployer, 'gas_price':1000000000})

    print('bank', bank.address)
    print('bank_config', bank_config.address)
    print('all ht', add_strat.address)
    print('liq', liq_strat.address)
    print('withdraw', rem_strat.address)

    # bank 0x87b8D8337A8086385326fC23b0c95A39cCA2D45D
    # bank_config 0x86e2Cd710a6fC950506c718b81A8E791b0F24884
    # all ht 0x13e60be414955aF08261b9B2B01C012c9B2E1D0E
    # liq 0x272fFA2cf090815e5cac7B89aD5e3266800f0fF4
    # withdraw 0x1d151C966B875188583E35500B3473eB84E75d71
    return bank, add_strat, liq_strat, rem_strat, bank_config, goblin_config, oracle


def deploy_pools(deployer, bank, add_strat, liq_strat, rem_strat, bank_config, goblin_config, oracle, pools):
    wht = interface.IAny(wht_address)

    registry = {}

    for pool in pools:
        print('==============================')
        print('deploying pool', pool['name'])
        fToken = interface.IAny(pool['token'])

        if pool['pid'] == 1:
            # reinvest 0.3% (avg gas fee ~0.006 BNB)
            print('deploying PancakeswapPool1Goblin ...')
            goblin = PancakeswapPool1Goblin.deploy(
                bank, chef_address, router_address, add_strat, liq_strat, 30, {'from': deployer, 'gas_price':1000000000})
        else:
            # reinvest 0.3% (avg gas fee ~0.006 BNB)
            print('deploying PancakeswapGoblin ...')
            goblin = PancakeswapGoblin.deploy(
                bank, chef_address, router_address, pool['pid'], add_strat, liq_strat, 30, {'from': deployer, 'gas_price':1000000000})
        print('goblin_config.setConfigs ...')
        goblin_config.setConfigs([goblin], [pool['goblinConfig']], {'from': deployer, 'gas_price':1000000000})
        
        print('deploying StrategyAddTwoSidesOptimal ...')
        add_strat_2 = StrategyAddTwoSidesOptimal.deploy(
            router_address, goblin, fToken, {'from': deployer, 'gas_price':1000000000})
        print('goblin.setStrategyOk ...')
        goblin.setStrategyOk([add_strat_2, rem_strat], True, {'from': deployer, 'gas_price':1000000000})
        print('bank_config.setGoblins ...')
        bank_config.setGoblins([goblin], [goblin_config], {'from': deployer, 'gas_price':1000000000})

        # re-assign two side strat as add strat for pool 1 goblin
        if pool['pid'] == 1:
            print('goblin.setCriticalStrategies ...')
            goblin.setCriticalStrategies(add_strat_2, liq_strat, {'from': deployer, 'gas_price':1000000000})
            print('goblin.setStrategyOk ...')
            goblin.setStrategyOk([add_strat], False, {'from': deployer, 'gas_price':1000000000})  # unset add_strat

        registry[pool['name']] = {'goblin': goblin,
                                  'two_side': add_strat_2, 
                                  'token': fToken.address}
        print('registry[',pool["name"],']:',registry[pool['name']])
    return registry


def test_cake_2(bank, registry):
    alice = accounts[1]

    prevBNBBal = alice.balance()

    bank.work(0, registry['sashimi']['goblin'], 0, 0, eth_abi.encode_abi(['address', 'bytes'], [
              registry['sashimi']['two_side'].address, eth_abi.encode_abi(['address', 'uint256', 'uint256'], [sashimi_address, 0, 0])]), {'from': alice, 'value': '1 ether'})

    curBNBBal = alice.balance()

    print('∆ ht alice', curBNBBal - prevBNBBal)
    print('alice pos', bank.positionInfo(1))

    assert almostEqual(curBNBBal - prevBNBBal, -10**18), 'incorrect BNB input amount'

    # test reinvest
    chain.mine(10)

    goblin = interface.IAny(registry['sashimi']['goblin'])
    goblin.reinvest({'from': alice})


def test_busd(bank, registry, add_strat):
    alice = accounts[1]

    prevBNBBal = alice.balance()

    bank.work(0, registry['busd']['goblin'], 0, 0, eth_abi.encode_abi(['address', 'bytes'], [
              add_strat.address, eth_abi.encode_abi(['address', 'uint256'], [busd_address, 0])]), {'from': alice, 'value': '1 ether'})

    curBNBBal = alice.balance()

    print('∆ ht alice', curBNBBal - prevBNBBal)
    print('alice pos', bank.positionInfo(1))

    assert almostEqual(curBNBBal - prevBNBBal, -10**18), 'incorrect BNB input amount'


def test_busd_2(bank, registry):
    alice = accounts[1]

    prevBNBBal = alice.balance()

    bank.work(0, registry['busd']['goblin'], 0, 0, eth_abi.encode_abi(['address', 'bytes'], [
              registry['busd']['two_side'].address, eth_abi.encode_abi(['address', 'uint256', 'uint256'], [sashimi_address, 0, 0])]), {'from': alice, 'value': '1 ether'})

    curBNBBal = alice.balance()

    print('∆ ht alice', curBNBBal - prevBNBBal)
    print('alice pos', bank.positionInfo(1))

    assert almostEqual(curBNBBal - prevBNBBal, -10**18), 'incorrect BNB input amount'


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

    # ====================================
    # 部署相关合约
    # bank, add_strat, liq_strat, rem_strat, bank_config, goblin_config, oracle = deploy(deployer)
    # 或者关联到已部署合约
    bank_config = ConfigurableInterestBankConfig.at('0x50D73FF608c6a66b1c36f4a051363cC8a359621d')
    bank = TransparentUpgradeableProxyImpl.at('0xF1FB892E5072cE129Af13a795f211598A8931132')
    bank = interface.IAny(bank)
    oracle = SimplePriceOracle.at('0xf3e2206a87014A3acE8def4Bd65BE84CC9B2b388')
    add_strat = StrategyAllHTOnly.at('0x7Bc24bB9da86C808cf8cBC9ED935AC61068FCD34')
    liq_strat = StrategyLiquidate.at('0x04492d6C6bB5439e5916CC792b570DEd6a3563f6')
    rem_strat = StrategyWithdrawMinimizeTrading.at('0x5158e8E7a7C45050Cd039802530473b01570f1f2')
    goblin_config = PancakeswapGoblinConfig.at('0x21952994097720Db2356B73617F7d03ee9662Eaa')
    print('bank', bank.address)
    print('bank_config', bank_config.address)
    print('all ht', add_strat.address)
    print('liq', liq_strat.address)
    print('withdraw', rem_strat.address)
    print('goblin_config', goblin_config.address)
    # ====================================

    

    pools = [
        {
            'name': 'sashimi',
            'token': sashimi_address,
            'lp': sashimi_lp_address,
            'pid': 1,
            'goblinConfig': [True, 6250, 7000, 11000]
        }
        # ====================================
        #  屏蔽无需测试的token
        # ,
        # {
        #     'name': 'busd',
        #     'token': busd_address,
        #     'lp': busd_lp_address,
        #     'pid': 2,
        #     'goblinConfig': [True, 7000, 8000, 11000]
        # },
        # {
        #     "name": "btcb",
        #     "token": btcb_address,
        #     "lp": btcb_lp_address,
        #     "pid": 15,
        #     "goblinConfig": [True, 7000, 8000, 11000]
        # },
        # {
        #     "name": "eth",
        #     "token": eth_address,
        #     "lp": eth_lp_address,
        #     "pid": 14,
        #     "goblinConfig": [True, 7000, 8000, 11000]
        # },
        # {
        #     "name": "usdt",
        #     "token": usdt_address,
        #     "lp": usdt_lp_address,
        #     "pid": 17,
        #     "goblinConfig": [True, 7000, 8000, 11000]
        # },
        # {
        #     "name": "alpha",
        #     "token": alpha_address,
        #     "lp": alpha_lp_address,
        #     "pid": 16,
        #     "goblinConfig": [True, 6250, 7000, 11000]
        # }
        # ====================================
        ]

    # ====================================
    # deploy pools
    # registry = deploy_pools(deployer, bank, add_strat, liq_strat, rem_strat,
    #                         bank_config, goblin_config, oracle, pools)
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
    fToken = interface.IAny(sashimi_address)

    # oracle.setPrices([wht], [fToken], [10**18 * 300], {'from': deployer, 'gas_price':1000000000})
    
    # # set whitelist tokens to add_strat (no sashimi)
    # add_fTokens = list(map(lambda pool: pool['token'], pools[1:]))
    # print('add_fTokens:', add_fTokens)
    # print('add_strat.setWhitelistTokens ...')
    # add_strat.setWhitelistTokens(add_fTokens, [True] * len(add_fTokens), {'from': deployer, 'gas_price':1000000000})

    # # set whitelist tokens to liq_strat, rem_strat
    # fTokens = list(map(lambda pool: pool['token'], pools))
    # print('fTokens:', fTokens)
    # print('liq_strat.setWhitelistTokens ...')
    # liq_strat.setWhitelistTokens(fTokens, [True] * len(fTokens), {'from': deployer, 'gas_price':1000000000})
    # print('rem_strat.setWhitelistTokens ...')
    # rem_strat.setWhitelistTokens(fTokens, [True] * len(fTokens), {'from': deployer, 'gas_price':1000000000})

    #########################################################################
    # test work

    print('开始测试token: sashimi ...')
    print('bank.nextPositionID=',bank.nextPositionID())
    print('goblin.health()=',goblin.health(1)) 
    print('goblin.shares[]=',goblin.shares(1))  
    print('goblin.shareToBalance(goblin.shares[])=',goblin.shareToBalance(goblin.shares(1)))  
    
    # test_token_1(bank, registry, 'sashimi')  # make sure remaining debt is not too small
    # print('测试token ...')
    # test_token(bank, registry, add_strat, liq_strat, rem_strat, 'sashimi')

